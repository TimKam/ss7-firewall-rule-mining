#!/usr/bin/python3

## Reads a csv or msg pack file and store it as a csv file but first it orders it based on a 
# specified column and also adds a diff_time columns which tells the time between two signals (in micro sec)
# use --help to see input arguments

from pandas import read_msgpack, read_csv
import argparse
import os
import sys
from pandas import datetime

## Returns the difference in time between to signals for a vector of values
# @param[in] dfTime     Dataframe vector containing the time_stamps
# @param[in] dfSortOn   Dataframe vector containing the values to sort on
# @param[out] diff      the difference in time in micro sec between two calling Global Times
#
def getDiffTime(dfTime,dfSortOn):
    diff = list()
    diff.append(-1) #mark the timediff with minus 1 when start, this is the first
    interval = 1
    prev_sorted_val = dfSortOn[0]
    for i in range(interval, len(dfTime)):
       # print(dfTime[i])
        time_diff = datetime.fromtimestamp(dfTime[i]) - datetime.fromtimestamp(dfTime[i - interval])
        #time_diff = datetime.strptime(dfTime[i], '%S.%f') - datetime.strptime(dfTime[i - interval], '%S.%f')
        elapsed_us = (time_diff.days * 86400000000) + (time_diff.seconds * 1000000) + (time_diff.microseconds)
    
        if prev_sorted_val != dfSortOn[i]:  #if new ue id set the timediff -1 to mark that it is a new flow
            elapsed_us = -1 #new ue_id
            prev_sorted_val = dfSortOn[i]
      
        diff.append(elapsed_us)
    return diff

## Sorts a msg pack file and stores it as a csv file, removes all lines that does not have a cgGT value (-1)
# @param[in] input_file  either a csv or a msgpack file containing data that is going to be stored
# @param[in] file_type  Either "csv" of "pack", defines the type of file to read as input
# @param[in] sort_on    What column to sort on
# @param[in] file_out   The output file name (csv file)
# 
def sort_file(input_file, file_type, sort_on, file_out):
    if file_type == "pack":
        readDf = read_msgpack(input_file)
    else:
        readDf = read_csv(input_file) 
        
    filteredDf = readDf.loc[readDf[sort_on] != "00" ]

    sortedDf = filteredDf.sort_values(by=[sort_on, 'time_stamp'])
    sortedDf.reset_index(drop=True, inplace=True)

    #add diff times as new column
    diffTimes = getDiffTime(sortedDf['time_stamp'],sortedDf[sort_on])
    sortedDf['diff_time'] = diffTimes

    export_csv = sortedDf.to_csv (file_out, index = None, header=True)
    print("Sorted csv is stored in file: ", file_out) 


## Verifies that the input file either ends with .csv or .pack
# @param[in] file_name  name of the file that should be tested
# 
def checkInputFile(file_name):
    file_parts = file_name.split('.')
    allOk = False
    if len(file_parts) == 2:
        file_type = file_parts[1]
        if file_type == "csv" or file_type == "pack":
            allOk = True
    if allOk == False:
        print("input file name is not correct, should only contain one . and should end with .csv or .pack")
        sys.exit(-1)
    return file_parts[0], file_parts[1]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='msg_pack reader')
    parser.add_argument('--file', metavar='<file to sort>',
                        help='should be either msg pack file (end with .pack) or csv file (end with .csv)', required=True)
    parser.add_argument('--out', metavar='<out put file name>',
                        help='out put file name where the parsed data is stored, output is stored in a csv file', default="ss7_filtered_data.csv")
    parser.add_argument('--sort_on', metavar='<what to sort on>',
                        help='can sort on any column in file, check header in file, common values are "cgGT", "imsi" time_stamp is always used to sort on after first sorting has been done.', type=str, default="cgGT")

    
    args = parser.parse_args()
    
    input_file = args.file
    file_out = args.out
    sort_on = args.sort_on

    if not os.path.isfile(input_file):
        print(format(input_file)," does not exist")
        sys.exit(-1)

    file_name, file_type = checkInputFile(input_file)
    print("filename: ", input_file)
    sort_file(input_file, file_type, sort_on, file_out)
    sys.exit(0)

