#!/usr/bin/python3

## Reads a msgpack file and store it as a csv file but first it orders it based on Calling Global Title (cgGT)

from pandas import read_msgpack
import argparse
import os
import sys
from pandas import datetime

## Returns the difference in time between to calls for the same cgGT
# @param[in] dfTime Dataframe vector containing the time_stamps
# @param[in] dfcgGT Dataframe vector containing the calling Global Titles
# @param[out] diff the difference in time in nano sec between two calling Global Times
#
def getDiffTime(dfTime,dfcgGT):
    diff = list()
    diff.append(-1) #mark the timediff with minus 1 when start, this is the first
    interval = 1
    cgGT = dfcgGT[0]
    for i in range(interval, len(dfTime)):
       # print(dfTime[i])
        time_diff = datetime.fromtimestamp(dfTime[i]) - datetime.fromtimestamp(dfTime[i - interval])
        #time_diff = datetime.strptime(dfTime[i], '%S.%f') - datetime.strptime(dfTime[i - interval], '%S.%f')
        elapsed_us = (time_diff.days * 86400000000) + (time_diff.seconds * 1000000) + (time_diff.microseconds)
    
        if cgGT != dfcgGT[i]:  #if new ue id set the timediff -1 to mark that it is a new flow
            elapsed_us = -1 #new ue_id
            cgGT = dfcgGT[i]
      
        diff.append(elapsed_us)
    return diff

## Sorts a msg pack file and stores it as a csv file, removes all lines that does not have a cgGT value (-1)
# @param[in] file_name msgpack file containing data that is going to be stored in a csv file
# 
def sort_csv(file_name):
    readDf = read_msgpack(file_name)
    filteredDf = readDf.loc[readDf['cgGT'] != "00" ]

    sortedDf = filteredDf.sort_values(by=['cgGT', 'time_stamp'])
    sortedDf.reset_index(drop=True, inplace=True)

    #add diff times as new column
    diffTimes = getDiffTime(sortedDf['time_stamp'],sortedDf['cgGT'])
    sortedDf['diff_time'] = diffTimes

    export_csv = sortedDf.to_csv (file_out, index = None, header=True)
    print("Sorted csv is stored in file: ", file_out) 

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='msg_pack reader')
    parser.add_argument('--pack', metavar='<msg_pack file name>',
                        help='msg_pack file to read', required=True)
    parser.add_argument('--out', metavar='<out put file name>',
                        help='out put file name where the parsed data is stored', default="ss7_filtered_data.csv")
    args = parser.parse_args()
    
    file_name = args.pack
    file_out = args.out

    if not os.path.isfile(file_name):
        print(format(file_name)," does not exist")
        sys.exit(-1)

    sort_csv(file_name)
    sys.exit(0)

