"""

This script runs the WAV files from TIMIT database that are needed with VTR FORMANTS through a Gammatone FilterBank,
and saves the output (128*NBFrame floats for each WAV file) to the f2cnn/TRAIN or TEST directories,
with the .GFB.npy extension

The files should be first processed with OrganiseFiles.py

"""

import glob
import os
import struct
import subprocess
import time
import wave
from configparser import ConfigParser
from itertools import product
from multiprocessing.pool import Pool
from multiprocessing import cpu_count
from os import remove
from os.path import splitext, join, split
from shutil import copyfile
import numpy

from gammatone import filters


def GetFilteredOutputFromFile(filename, FILTERBANK_COEFFICIENTS):
    """
    Computes the output of a gammatone filterbank applied to the WAV file 'filename'
    :param FILTERBANK_COEFFICIENTS
    :param filename: path to a WAV file
    :return: number of frames in the file, and output matrix (128*nbframes) of the filterbank
    """
    # .WAV file to list
    try:
        wavFile = wave.open(filename, 'r')
    except wave.Error:
        print("Converting file to correct format...")
        ConvertWavFile(filename)
        wavFile = wave.open(filename, 'r')
    wavList = numpy.zeros(wavFile.getnframes())
    for i in range(wavFile.getnframes()):
        a = wavFile.readframes(1)
        a = struct.unpack("<h", a)[0]
        wavList[i] = a

    # # If plotting is needed
    # t = [i for i in range(len(wavList))]
    # plt.plot(t, wavList)
    # plt.show()

    return GetFilteredOutputFromArray(wavList, FILTERBANK_COEFFICIENTS), wavFile.getframerate()


def GetFilteredOutputFromArray(array, FILTERBANK_COEFFICIENTS):
    # gammatone library needs a numpy array
    # Application of the filterbank to a vector
    filteredMatrix = filters.erb_filterbank(array,
                                            FILTERBANK_COEFFICIENTS)  # Matrix of wavFile.getnframes() X 128 real values
    return filteredMatrix


def ConvertWavFile(filename):
    """
    Some WAV files seem to miss some features needed by the wave library (RIFF ID), this counters that
    :param filename: path to the WAV file
    """
    newname = splitext(filename)[0] + '.mp3'
    copyfile(filename, newname)
    remove(filename)
    FNULL = open(os.devnull, 'w')
    subprocess.call(['ffmpeg', '-i', newname, filename], stdout=FNULL, stderr=subprocess.STDOUT, close_fds=True)
    remove(newname)


def saveGFBMatrix(filename, matrix):
    numpy.save(filename, matrix)


def loadGFBMatrix(filename):
    return numpy.load(filename + '.npy')


def GammatoneFiltering(wavFile, FILTERBANK_COEFFICIENTS):
    gfbFilename = splitext(wavFile)[0] + '.GFB'
    print("Filtering:\t{}".format(wavFile))

    # Compute the filterbank output
    outputMatrix, _ = GetFilteredOutputFromFile(wavFile, FILTERBANK_COEFFICIENTS)

    # Save file to .GFB.npy format
    print("Saving:\t\t{}".format(gfbFilename))
    saveGFBMatrix(gfbFilename, outputMatrix)
    print("\t\t{}\tdone !".format(wavFile))


def FilterAllOrganisedFiles(testMode):
    TotalTime = time.time()

    if testMode:
        # Test WavFiles
        wavFiles = glob.glob(join("testFiles", "*.WAV"))
    else:
        # Get all the WAV files under resources
        wavFiles = glob.glob(join("resources", "f2cnn", "*", "*.WAV"))

    print("\n###############################\nApplying FilterBank to files in '{}'.".format(split(wavFiles[0])[0]))

    if not wavFiles:
        print("NO WAV FILES FOUND")
        exit(-1)

    print(len(wavFiles), "files found")

    # #### READING CONFIG FILE
    config = ConfigParser()
    config.read('F2CNN.conf')
    framerate = config.getint('FILTERBANK', 'FRAMERATE')
    nchannels = config.getint('FILTERBANK', 'NCHANNELS')
    lowcutoff = config.getint('FILTERBANK', 'LOW')
    # ##### PREPARATION OF FILTERBANK
    # CENTER FREQUENCIES ON ERB SCALE
    CENTER_FREQUENCIES = filters.centre_freqs(framerate, nchannels, lowcutoff)
    # Filter coefficient for a Gammatone filterbank
    FILTERBANK_COEFFICIENTS = filters.make_erb_filters(framerate, CENTER_FREQUENCIES)

    # Usage of multiprocessing, to reduce computing time
    proc = cpu_count()

    multiproc_pool = Pool(processes=proc)
    arguments = product(wavFiles, [FILTERBANK_COEFFICIENTS])
    multiproc_pool.starmap(GammatoneFiltering, arguments)

    print("Filtered and Saved all files.")
    print('                Total time:', time.time() - TotalTime)
    print('')