#!/usr/local/bin/python
# 
# Get Code42 Crashplan logs into Splunk
#
# Code written by:
#   Greg Jewett, jewettg@austin.utexas.edu, 512-471-9645
#
# Code maintained by:
#   Greg Jewett, jewettg@austin.utexas.edu, 512-471-9645
#
# Using libraries provided by Code42, get the logs out of CrashPlan appliances and
# into Splunk.  We can process the data after that.
#
# ---------------------------------------------------------------------------------------
# CHANGE LOG
# 2017-04-24 (GSJ) Initial version.
# 
# ---------------------------------------------------------------------------------------

# Modules and Libraries
# ---------------------------------------------------------------------------------------
# Import the print function from Python 3
# http://stackoverflow.com/questions/493386/how-to-print-without-newline-or-space
from __future__ import print_function


#import c42api
import requests
from requests.auth import HTTPBasicAuth


import datetime
import subprocess
import os
import logging
import argparse
import json

#import splunklib.client as client



# Required variables and environment setup
# ---------------------------------------------------------------------------------------

# Script Version
scriptVer = "1.0"


# Functions used by global path variables.
# ---------------------------------------------------------------------

# Get Script Path
def scriptPath():
	return os.path.dirname(os.path.realpath(__file__))

# function to return a string (date/time) stamp, based on format needed.
def dt_stamp(format):
	stamp = datetime.datetime.now()
	if format == "d":
		# current date in ISO (YYYY-MM-DD) format
		return stamp.strftime("%Y-%m-%d")
	if format == "dt":
		# current date/time in ISO format: YYYY-MM-DDTHH:MM:SS.ddddd
		return stamp.isoformat()
	if format == "t":
		# current time in ISO format: HH:MM:SS.ddddd
		return stamp.strftime("%H:%M:%S.%f")
	if format == "fdt":
		# current date and time in format supported by OS for filenames.
		return stamp.strftime("%Y-%m-%d_%H%M%S")

# Setup global path variables
# ---------------------------------------------------------------------

# Create a path where logs will be written.
logPath = scriptPath()+"/log"
logFileSuffix = "_crashplan_fetch.log"

# File that will be created to in case of script failure, to prevent future executions.
scriptFileFlagFile = scriptPath()+"/Script_Error_Flag"

# Script Version
script_version = "1.0"

# Functions
# -------------------------------------------------------------------------------------

def includeHeader():
	# This function is for logging purposes only. 
	# There are specific log lines that should only need to be output
	# once per log file, thus reducing the size of the log files.
	
	# It checks the size of the log file, if it is smaller than the 
	# approximate size of the log file with the header lines, 
	# return boolean (whether or not to include log lines).

	logFile = logPath+"/"+dt_stamp('d')+logFileSuffix
	size = 0
	if os.path.exists(logFile):
		f = open(logFile) 
		f.seek(0, os.SEEK_END)
		size = f.tell()
	return (size < 215)
	# The file size of a log file that includes a header is about 209 bytes
	# Checking to see if a file has header, by looking at its size.


def doLog(level, message, scriptError=False):
    # This function perform basic logging. in addition to the writing out
    # a "stop file" if a "scriptError" condition is met.

	# Setup logging configuration
	loggingEnabled = False
	logFile = logPath+"/"+dt_stamp('d')+logFileSuffix

	# Check to see if the logging path is available to write to, if not
	# then output an error to the console.
	if os.path.exists(logPath):
		aLogger = logging.basicConfig(filename=logFile,
		                              level=logging.DEBUG,
									  format='%(asctime)s %(levelname)8s: %(message)s')
		loggingEnabled = True
	else:
		print("WARNING: Logging disabled!  Log path not found: "+logPath)

	# Logging path found, write out the logging message.
	if loggingEnabled:
		if level == "debug":
			logging.debug(message)
		if level == "info":
			logging.info(message)
		if level == "warning":
			logging.warning(message)
		if level == "error":
			logging.error(message)
		if level == "critical":
			logging.critical(message)

	# If a "scriptError" condition has been detected, then create 
	# a "Script Error Flag File" that will halt the script, but give
	# us some explanation on why it was halted.
	if scriptError:
		sef = open(scriptFileFlagFile, "w")
		sef.write("\r\n\r\nScript Error Flag File\r\n")
		sef.write(dt_stamp('fdt')+"\r\n")
		sef.write(message+"\r\n")
		sef.close()
		exit(code=1)

# ===========================================================================
# ===========================================================================
# Check the Intermediate Forwarders 
# ===========================================================================
# ===========================================================================

# Check to see if the ScriptErrorFlag file is present, if so, halt the script!
if os.path.exists(scriptFileFlagFile):
	doLog("critical", "Script error flag file found!  Halting script execution!")
	exit(code=1)

if includeHeader():
	doLog("info", "Crashplan Log Fetch Script")
	
# Setup conditions to continue, which are flipped if errors occur
# when trying to check the forwarders or launch the script.
scriptError = False

# Check to see if the ScriptErrorFlag file is present, if so, halt the script!
if os.path.exists(scriptFileFlagFile):
	scriptError = True
	doLog("critical", "Script error flag file found!  Halting script execution!")
	exit(code=1)


# Get authentication token 
# ---------------------------------------------------------------------

authCredentials = ("splunkadmin", "R3in|!C@k32")
cpURL = "https://utbackup01.its.utexas.edu:4285/api/authToken"
caBundle = scriptPath()+"/cp_ca_bundle.pem"


try:
	doLog("info", "Attempting connection to Crashplan Server: "+cpURL)
	httpRequest = requests.post(cpURL, auth=authCredentials, verify=caBundle)
except ConnectionError as err:
	doLog("critical", "API Connection Error: "+str(err))
	exit(1)
	
status_code = httpRequest.status_code
if status_code == 200:
	doLog("info", "Successful connection to Crashplan Server: "+str(status_code))
	rDecode = json.loads(httpRequest.text)
	token1,token2 = rDecode['data']
	doLog("info", "Retrieved tokens: "+token1+"-"+token2)
else:
	doLog("critical", "API Connection Error, status code: "+status_code) 
	exit(1)
	

# cpURL = "https://utbackup01.its.utexas.edu:4285/api/Computer"
# headers = {"Authorization": "token "+token1+"-"+token2}
# computer = requests.get(cpURL, verify=caBundle, headers=headers)
# 
# someJSON = json.loads(computer.text)
# for x in someJSON['data']['computers']:
# 	print("{: >15} {: >5} {: >40} {: >20} {: >30}".format(str(x['address']), x['active'], x['name'], x['orgUid'], x['osName']))
	 

# cpURL = "https://utbackup01.its.utexas.edu:4285/api/LogFile/request.log"
# headers = {"Authorization": "token "+token1+"-"+token2}
# logs = requests.get(cpURL, verify=caBundle, headers=headers)
# 
# someJSON = json.loads(logs.text)
# print(json.dumps(someJSON, sort_keys=True, indent=4))

cpURL = "https://utbackup01.its.utexas.edu:4285/api/User?active=true&pgSize=999&roleId=1&incRoles=true"
headers = {"Authorization": "token "+token1+"-"+token2}
logs = requests.get(cpURL, verify=caBundle, headers=headers)

someJSON = json.loads(logs.text)
print(json.dumps(someJSON, sort_keys=True, indent=4))






