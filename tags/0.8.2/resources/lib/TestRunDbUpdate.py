import unittest
import os, sys
import re, string


# Shared resources
BASE_RESOURCE_PATH = os.path.join( os.getcwd(), ".." )
sys.path.append( os.path.join( BASE_RESOURCE_PATH, "lib" ) )
sys.path.append( os.path.join( BASE_RESOURCE_PATH, "lib", "pyscraper" ) )
# append the proper platforms folder to our path, xbox is the same as win32
env = ( os.environ.get( "OS", "win32" ), "win32", )[ os.environ.get( "OS", "win32" ) == "xbox" ]
if env == 'Windows_NT':
	env = 'win32'
sys.path.append( os.path.join( BASE_RESOURCE_PATH, "platform_libraries", env ) )


from pysqlite2 import dbapi2 as sqlite
from gamedatabase import *
from util import *
import dbupdate
import config


class RCBMock:
	
	itemCount = 0
	
	def writeMsg(self, msg1, msg2, msg3, count=0):
		return True


#adjust settings for tests
util.RCBHOME = os.path.join(os.getcwd(), '..', '..')
#util.ISTESTRUN = True

Logutil.currentLogLevel = util.LOG_LEVEL_INFO


#Init database
databasedir = os.path.join( os.getcwd())
gdb = GameDataBase(databasedir)
gdb.connect()
gdb.dropTables()		
gdb.createTables()


configFile = config.Config()
statusOk, errorMsg = configFile.readXml()
if(statusOk == True):
	dbupdate.DBUpdate().updateDB(gdb, RCBMock(), 0, configFile.romCollections)



