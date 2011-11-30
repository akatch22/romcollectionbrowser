
import os, sys, re
import getpass, string, glob
import codecs
import zipfile
import zlib
import time

import util
from util import *
from config import *
from gamedatabase import *
from descriptionparserfactory import *
from pyscraper import *



class DBUpdate:
	
	def __init__(self):
		pass
	
	Settings = util.getSettings()
	
	def updateDB(self, gdb, gui, updateOption, romCollections):
		self.gdb = gdb
			
		#self.scrapeResultsFile = self.openFile(os.path.join(util.getAddonDataPath(), 'scrapeResults.txt'))
		self.missingDescFile = self.openFile(os.path.join(util.getAddonDataPath(), 'scrapeResult_missingDesc.txt'))
		self.missingArtworkFile = self.openFile(os.path.join(util.getAddonDataPath(), 'scrapeResult_missingArtwork.txt'))
		self.possibleMismatchFile = self.openFile(os.path.join(util.getAddonDataPath(), 'scrapeResult_possibleMismatches.txt'))		
		
		Logutil.log("Start Update DB", util.LOG_LEVEL_INFO)
		
		Logutil.log("Iterating Rom Collections", util.LOG_LEVEL_INFO)
		rccount = 1
		
		#get fuzzyFactor before scraping
		matchingRatioIndex = self.Settings.getSetting(util.SETTING_RCB_FUZZYFACTOR)
		if (matchingRatioIndex == ''):
			matchingRatioIndex = 2
		fuzzyFactor = util.FUZZY_FACTOR_ENUM[int(matchingRatioIndex)]
		
		enableFullReimport = self.Settings.getSetting(util.SETTING_RCB_ENABLEFULLREIMPORT).upper() == 'TRUE'
		
		continueUpdate = True
		
		for romCollection in romCollections.values():
			
			#timestamp1 = time.clock()
			
			#check if import was canceled
			if(not continueUpdate):
				Logutil.log('Game import canceled', util.LOG_LEVEL_INFO)
				break
							
			#prepare Header for ProgressDialog
			progDialogRCHeader = "Importing Rom Collection (%i / %i): %s" %(rccount, len(romCollections), romCollection.name)
			rccount = rccount + 1
			
			Logutil.log("current Rom Collection: " +romCollection.name, util.LOG_LEVEL_INFO)
			
			#self.scrapeResultsFile.write('~~~~~~~~~~~~~~~~~~~~~~~~\n' +romCollection.name +'\n' +'~~~~~~~~~~~~~~~~~~~~~~~~\n')
			self.missingDescFile.write('~~~~~~~~~~~~~~~~~~~~~~~~\n' +romCollection.name +'\n' +'~~~~~~~~~~~~~~~~~~~~~~~~\n')
			self.missingArtworkFile.write('~~~~~~~~~~~~~~~~~~~~~~~~\n' +romCollection.name +'\n' +'~~~~~~~~~~~~~~~~~~~~~~~~\n')
			self.possibleMismatchFile.write('~~~~~~~~~~~~~~~~~~~~~~~~\n' +romCollection.name +'\n' +'~~~~~~~~~~~~~~~~~~~~~~~~\n')
			self.possibleMismatchFile.write('gamename, filename\n')

			#Read settings for current Rom Collection
			Logutil.log("ignoreOnScan: " +str(romCollection.ignoreOnScan), util.LOG_LEVEL_INFO)
			if(romCollection.ignoreOnScan):
				Logutil.log("current Rom Collection will be ignored.", util.LOG_LEVEL_INFO)
				#self.scrapeResultsFile.write('Rom Collection will be ignored.\n')
				continue

			Logutil.log("update is allowed for current rom collection: " +str(romCollection.allowUpdate), util.LOG_LEVEL_INFO)
			Logutil.log("max folder depth: " +str(romCollection.maxFolderDepth), util.LOG_LEVEL_INFO)
			
			if enableFullReimport == False:
				RCId = romCollection.id
			else:
				RCId = None
			
			files = self.getRomFilesByRomCollection(romCollection.romPaths, romCollection.maxFolderDepth, RCId=RCId)
			
			#itemCount is used for percentage in ProgressDialogGUI
			gui.itemCount = len(files) +1
			
			#self.scrapeResultsFile.write('%s games total' %(str(len(fileGamenameDict))))
			
			#check if first scraper is a multigame scraper
			firstScraper = romCollection.scraperSites[0]
			if(not firstScraper.descFilePerGame):
				
				#build file hash tables	(key = gamename or crc, value = romfiles)			
				Logutil.log("Start building file dict", util.LOG_LEVEL_INFO)
				fileDict = self.buildFileDict(gui, progDialogRCHeader, files, romCollection, firstScraper)
									
				try:
					fileCount = 1
					gamenameFromDesc = ''
					
					#TODO move to to check preconditions
					#first scraper must be the one for multiple games					
					if(len(firstScraper.scrapers) == 0):
						Logutil.log('Configuration error: Configured scraper site does not contain any scrapers', util.LOG_LEVEL_ERROR)
						continue
											
					scraper = firstScraper.scrapers[0]
					Logutil.log("start parsing with multi game scraper: " +str(firstScraper.name), util.LOG_LEVEL_INFO)
					Logutil.log("using parser file: " +scraper.parseInstruction, util.LOG_LEVEL_INFO)
					Logutil.log("using game description: " +scraper.source, util.LOG_LEVEL_INFO)
											
					parser = DescriptionParserFactory.getParser(str(scraper.parseInstruction)) 										
					
					#parse description
					for result in parser.scanDescription(scraper.source, str(scraper.parseInstruction), scraper.encoding):
						
						try:
							gamenameFromDesc = result['Game'][0]
							
							#find parsed game in Rom Collection
							filenamelist = self.matchDescriptionWithRomfiles(firstScraper, result, fileDict, gamenameFromDesc)
		
							artScrapers = {}
		
							if(filenamelist != None and len(filenamelist) > 0):
												
								gamenameFromFile = self.getGamenameFromFilename(filenamelist[0], romCollection)
								foldername = self.getFoldernameFromRomFilename(filenamelist[0])
								
								continueUpdate = gui.writeMsg(progDialogRCHeader, "Import game: " +str(gamenameFromDesc), "", fileCount)
								if(not continueUpdate):				
									Logutil.log('Game import canceled by user', util.LOG_LEVEL_INFO)
									break
								
								fileCount = fileCount +1
								
								Logutil.log('Start scraping info for game: ' +str(gamenameFromFile), LOG_LEVEL_INFO)
															
								#check if this file already exists in DB
								continueUpdate, isUpdate, gameId = self.checkRomfileAlreadyExists(filenamelist[0], enableFullReimport)
								if(not continueUpdate):
									continue
								
								#use additional scrapers
								if(len(romCollection.scraperSites) > 1):
									result, artScrapers = self.useSingleScrapers(result, romCollection, 1, gamenameFromFile, foldername, filenamelist[0], fuzzyFactor, updateOption, gui, progDialogRCHeader, fileCount)
								
							else:
								Logutil.log("game " +gamenameFromDesc +" was found in parsed results but not in your rom collection.", util.LOG_LEVEL_WARNING)
								continue						
							
							dialogDict = {'dialogHeaderKey':progDialogRCHeader, 'gameNameKey':gamenameFromFile, 'scraperSiteKey':artScrapers, 'fileCountKey':fileCount}
							gameId, continueUpdate = self.insertGameFromDesc(result, gamenameFromFile, romCollection, filenamelist, foldername, isUpdate, gameId, gui, dialogDict)
							if(not continueUpdate):
								break
							
							#remove found files from file list
							if(gameId != None):
								for filename in filenamelist:
									files.remove(filename)
									
							#stop import if no files are left
							if(len(files) == 0):
								Logutil.log("All games are imported", util.LOG_LEVEL_INFO)
								break
						
						except Exception, (exc):
							Logutil.log("an error occured while adding game " +gamenameFromDesc, util.LOG_LEVEL_WARNING)
							Logutil.log("Error: " +str(exc), util.LOG_LEVEL_WARNING)
							continue
						
					#all files still available files-list, are missing entries
					for filename in files:
						gamenameFromFile = self.getGamenameFromFilename(filename, romCollection)
						self.missingDescFile.write('%s\n' %gamenameFromFile)
							
				except Exception, (exc):
					Logutil.log("an error occured while adding game " +gamenameFromDesc, util.LOG_LEVEL_WARNING)
					Logutil.log("Error: " +str(exc), util.LOG_LEVEL_WARNING)
					self.missingDescFile.write('%s\n' %gamenameFromDesc)
					continue
			else:	
				fileCount = 1
				successfulFiles = 0
				lastgamename = ''
				lastGameId = None
				
				for filename in files:
					
					try:
						gamenameFromFile = ''
						gamenameFromFile = self.getGamenameFromFilename(filename, romCollection)
						
						#check if we are handling one of the additional disks of a multi rom game
						isMultiRomGame = self.checkRomfileIsMultirom(gamenameFromFile, lastgamename)
						lastgamename = gamenameFromFile
						
						if(isMultiRomGame):
							if(lastGameId == None):
								Logutil.log('Game detected as multi rom game, but lastGameId is None.', util.LOG_LEVEL_ERROR)
								continue
							fileType = FileType()
							fileType.id = 0
							fileType.name = "rcb_rom"
							fileType.parent = "game"
							self.insertFile(filename, lastGameId, fileType, None, None, None)
							continue
						
						Logutil.log('Start scraping info for game: ' + gamenameFromFile, LOG_LEVEL_INFO)						
						
						continueUpdate = gui.writeMsg(progDialogRCHeader, "Import game: " +gamenameFromFile, "", fileCount)
						if(not continueUpdate):				
							Logutil.log('Game import canceled by user', util.LOG_LEVEL_INFO)
							break
						
						#check if this file already exists in DB
						continueUpdate, isUpdate, gameId = self.checkRomfileAlreadyExists(filename, enableFullReimport)
						if(not continueUpdate):
							continue										
						
						results = {}
						foldername = os.path.dirname(filename)
						filecrc = ''
						
						results, artScrapers = self.useSingleScrapers(results, romCollection, 0, gamenameFromFile, foldername, filename, fuzzyFactor, updateOption, gui, progDialogRCHeader, fileCount)
						
						#print results
						if(len(results) == 0):
							lastgamename = ""
							gamedescription = None
						else:						
							gamedescription = results
							
						filenamelist = []
						filenamelist.append(filename)
						fileCount = fileCount +1
	
						#Variables to process Art Download Info
						dialogDict = {'dialogHeaderKey':progDialogRCHeader, 'gameNameKey':gamenameFromFile, 'scraperSiteKey':artScrapers, 'fileCountKey':fileCount}
						#Add 'gui' and 'dialogDict' parameters to function
						lastGameId, continueUpdate = self.insertGameFromDesc(gamedescription, gamenameFromFile, romCollection, filenamelist, foldername, isUpdate, gameId, gui, dialogDict)
						if (not continueUpdate):
							break
						
						if (lastGameId != None):
							successfulFiles = successfulFiles + 1
							
						#check if all first 10 games have errors
						if (fileCount >= 10 and successfulFiles == 0):
						 	answer = xbmcgui.Dialog().yesno(util.SCRIPTNAME, 'First 10 games could not be imported.', 'Continue anyway?')
						 	if(answer == False):
						 		xbmcgui.Dialog().ok(util.SCRIPTNAME, 'Import canceled.', 'Please check xbmc.log for errors.')
						 		continueUpdate = False
						 		break
						
					except Exception, (exc):
						Logutil.log("an error occured while adding game " +gamenameFromFile, util.LOG_LEVEL_WARNING)
						Logutil.log("Error: " +str(exc), util.LOG_LEVEL_WARNING)
						self.missingDescFile.write('%s\n' %gamenameFromFile)
						continue
					
			#timestamp2 = time.clock()
			#diff = (timestamp2 - timestamp1) * 1000		
			#print "load %i games in %d ms" % (self.getListSize(), diff)
					
		gui.writeMsg("Done.", "", "", gui.itemCount)
		self.exit()
		return True, ''
	
	
	def buildFileDict(self, gui, progDialogRCHeader, files, romCollection, firstScraper):
		
		fileCount = 1
		lastgamename = ""
		crcOfFirstGame = {}
		
		fileDict = {}
		
		for filename in files:
			try:
				gui.writeMsg(progDialogRCHeader, "Building file list...", "", fileCount)
				fileCount = fileCount +1
				
				gamename = self.getGamenameFromFilename(filename, romCollection)
				#check if we are handling one of the additional disks of a multi rom game
				isMultiRomGame = self.checkRomfileIsMultirom(gamename, lastgamename)
				#lastgamename may be overwritten by parsed gamename
				lastgamename = gamename
				gamename = gamename.strip()
				gamename = gamename.lower()
				
				#Logutil.log('gamename in fileDict: ' +str(gamename), util.LOG_LEVEL_INFO)
									
				#build dictionaries (key=gamename, filecrc or foldername; value=filenames) for later game search
				if(firstScraper.useFoldernameAsCRC):
					foldername = self.getFoldernameFromRomFilename(filename)
					foldername = foldername.strip()
					foldername = foldername.lower()
					fileDict = self.buildFilenameDict(fileDict, isMultiRomGame, filename, foldername)
				elif(firstScraper.useFilenameAsCRC):
					fileDict = self.buildFilenameDict(fileDict, isMultiRomGame, filename, gamename)
				elif(firstScraper.searchGameByCRC):
					filecrc = self.getFileCRC(filename)
					#use crc of first rom if it is a multirom game
					if(not isMultiRomGame):
						crcOfFirstGame[gamename] = filecrc
						Logutil.log('Adding crc to crcOfFirstGame-dict: %s: %s' %(gamename, filecrc), util.LOG_LEVEL_INFO)
					else:
						filecrc = crcOfFirstGame[gamename]
						Logutil.log('Read crc from crcOfFirstGame-dict: %s: %s' %(gamename, filecrc), util.LOG_LEVEL_INFO)
						
					fileDict = self.buildFilenameDict(fileDict, isMultiRomGame, filename, filecrc)
				else:						
					fileDict = self.buildFilenameDict(fileDict, isMultiRomGame, filename, gamename)
			except Exception, (exc):
				Logutil.log("an error occured while building file list", util.LOG_LEVEL_WARNING)
				Logutil.log("Error: " +str(exc), util.LOG_LEVEL_WARNING)
				continue
		
		return fileDict
		
		
	
	
	def getRomFilesByRomCollection(self, romPaths, maxFolderDepth, RCId = None):
				
		Logutil.log("Rom path: " +str(romPaths), util.LOG_LEVEL_INFO)
				
		Logutil.log("Reading rom files", util.LOG_LEVEL_INFO)
		files = []
		for romPath in romPaths:
			files = self.walkDownPath(files, romPath, maxFolderDepth)
			
		
		if RCId != None:
			inDBFiles = DataBaseObject(self.gdb, '').getFileAllFilesByRCId(RCId)
			files = [f.decode('utf-8') for f in files if not f.decode('utf-8') in inDBFiles]			
		
		files.sort()
		Logutil.log("Files read: " +str(files), util.LOG_LEVEL_INFO)
		
		return files
		
		
	def walkDownPath(self, files, romPath, maxFolderDepth):
		
		Logutil.log("walkDownPath romPath: " +romPath, util.LOG_LEVEL_INFO)						
		
		dirname = os.path.dirname(romPath)
		Logutil.log("dirname: " +dirname, util.LOG_LEVEL_INFO)
		basename = os.path.basename(romPath)
		Logutil.log("basename: " +basename, util.LOG_LEVEL_INFO)						
				
		Logutil.log("checking sub directories", util.LOG_LEVEL_INFO)
		dirname = dirname.decode(sys.getfilesystemencoding()).encode('utf-8')
		for walkRoot, walkDirs, walkFiles in self.walklevel(dirname, maxFolderDepth):
			Logutil.log( "root: " + walkRoot, util.LOG_LEVEL_DEBUG)
			Logutil.log( "walkDirs: " +str(walkDirs), util.LOG_LEVEL_DEBUG)
			Logutil.log( "walkFiles: " +str(walkFiles), util.LOG_LEVEL_DEBUG)
									
			newRomPath = os.path.join(walkRoot, basename)
			Logutil.log( "newRomPath: " +str(newRomPath), util.LOG_LEVEL_DEBUG)
			
			#glob is same as "os.listdir(romPath)" but it can handle wildcards like *.adf
			allFiles = [f.decode(sys.getfilesystemencoding()).encode('utf-8') for f in glob.glob(newRomPath)]
			Logutil.log( "all files in newRomPath: " +str(allFiles), util.LOG_LEVEL_DEBUG)
		
			#did not find appendall or something like this
			files.extend(allFiles)
		
		return files
	
	
	def walklevel(self, some_dir, level=1):
		some_dir = some_dir.rstrip(os.path.sep)
		assert os.path.isdir(some_dir)
		num_sep = len([x for x in some_dir if x == os.path.sep])
		for root, dirs, files in os.walk(some_dir):
			yield root, dirs, files
			num_sep_this = len([x for x in root if x == os.path.sep])
			if num_sep + level <= num_sep_this:
				del dirs[:]
		
		
	def getGamenameFromFilename(self, filename, romCollection):		
					
		Logutil.log("current rom file: " + filename, util.LOG_LEVEL_INFO)

		#build friendly romname
		if(not romCollection.useFoldernameAsGamename):
			gamename = os.path.basename(filename)
		else:
			gamename = os.path.basename(os.path.dirname(filename))
			
		Logutil.log("gamename (file): " +gamename, util.LOG_LEVEL_INFO)
				
		#use regular expression to find disk prefix like '(Disk 1)' etc.		
		match = False
		if(romCollection.diskPrefix != ''):
			match = re.search(romCollection.diskPrefix.lower(), gamename.lower())
		
		if match:
			gamename = gamename[0:match.start()]
		else:
			gamename = os.path.splitext(gamename)[0]					
		
		gamename = gamename.strip()
		
		Logutil.log("gamename (friendly): " +gamename, util.LOG_LEVEL_INFO)		
		
		return gamename
		
		
	def checkRomfileIsMultirom(self, gamename, lastgamename):		
	
		#XBOX Hack: rom files will always be named default.xbe: always detected as multi rom without this hack
		if(gamename == lastgamename and lastgamename.lower() != 'default'):		
			Logutil.log("handling multi rom game: " +lastgamename, util.LOG_LEVEL_INFO)			
			return True
		return False
		
		
	def buildFilenameDict(self, result, isMultiRomGame, filename, key):
		
		try:											
			if(not isMultiRomGame):
				filenamelist = []
				filenamelist.append(filename)
				result[key] = filenamelist
				Logutil.log('Add filename "%s" with key "%s"' %(filename, key), util.LOG_LEVEL_DEBUG)
			else:
				filenamelist = result[key]
				filenamelist.append(filename)
				result[key] = filenamelist
				Logutil.log('Add filename "%s" to multirom game with key "%s"' %(filename, key), util.LOG_LEVEL_DEBUG)
		except Exception, (exc):
			Logutil.log('Error occured in buildFilenameDict: ' +str(exc), util.LOG_LEVEL_WARNING)
			
		return result
		
		
	def getFileCRC(self, filename):
		
		try:
			#get crc value of the rom file - this can take a long time for large files, so it is configurable
			filecrc = ''		
			if (zipfile.is_zipfile(str(filename))):			
					Logutil.log("handling zip file", util.LOG_LEVEL_INFO)
					zip = zipfile.ZipFile(str(filename), 'r')
					zipInfos = zip.infolist()
					if(len(zipInfos) > 1):
						Logutil.log("more than one file in zip archive is not supported! Checking CRC of first entry.", util.LOG_LEVEL_WARNING)
					filecrc = "%0.8X" %(zipInfos[0].CRC & 0xFFFFFFFF)
					Logutil.log("crc in zipped file: " +filecrc, util.LOG_LEVEL_INFO)			
			else:						
				prev = 0
				for eachLine in open(str(filename),"rb"):
					prev = zlib.crc32(eachLine, prev)					
				filecrc = "%0.8X"%(prev & 0xFFFFFFFF)
				Logutil.log("crc for current file: " +str(filecrc), util.LOG_LEVEL_INFO)
			
			filecrc = filecrc.strip()
			filecrc = filecrc.lower()
		except Exception, (exc):
			Logutil.log("Error while creating crc: " +str(exc), util.LOG_LEVEL_ERROR)
			return "000000"
		
		return filecrc
		
		
	def getFoldernameFromRomFilename(self, filename):
		foldername = ''
		dirname = os.path.dirname(filename)		
		if(dirname != None):
			pathTuple = os.path.split(dirname)			
			if(len(pathTuple) == 2):
				foldername = pathTuple[1]				
				
		return foldername


	def matchDescriptionWithRomfiles(self, firstScraper, result, fileDict, gamenameFromDesc):
		
		filenamelist = []
		
		if(firstScraper.searchGameByCRC or firstScraper.useFoldernameAsCRC or firstScraper.useFilenameAsCRC):
			resultcrcs = result['crc']
			for resultcrc in resultcrcs:
				Logutil.log("crc in parsed result: " +resultcrc, util.LOG_LEVEL_DEBUG)
				resultcrc = resultcrc.lower()
				resultcrc = resultcrc.strip()
				filenamelist = self.findFilesByGameDescription(resultcrc, fileDict)
				if(filenamelist != None):
					break
		else:
			Logutil.log("game name in parsed result: " +gamenameFromDesc, util.LOG_LEVEL_INFO)
			gamenameFromDesc = gamenameFromDesc.lower()
			gamenameFromDesc = gamenameFromDesc.strip()
			filenamelist = self.findFilesByGameDescription(gamenameFromDesc, fileDict)
			
		return filenamelist


	def findFilesByGameDescription(self, key, fileDict):
		
		Logutil.log("searching for Key: " +str(key), util.LOG_LEVEL_INFO)
			
		try:
			filename = fileDict[key]
		except:
			filename = None
			
		if (filename != None):
			Logutil.log("result found: " +str(filename), util.LOG_LEVEL_INFO)				
		
		return filename
	
	
	def checkRomfileAlreadyExists(self, filename, enableFullReimport):
		
		isUpdate = False
		gameId = None
		
		romFile = File(self.gdb).getFileByNameAndType(filename, 0)
		if(romFile != None):
			isUpdate = True
			gameId = romFile[3]
			Logutil.log('File "%s" already exists in database.' %filename, util.LOG_LEVEL_INFO)
			Logutil.log('Always rescan imported games = ' +str(enableFullReimport), util.LOG_LEVEL_INFO)
			if(enableFullReimport == False):
				Logutil.log('Won\'t scrape this game again. Set "Always rescan imported games" to True to force scraping.', util.LOG_LEVEL_INFO)
				return False, isUpdate, gameId
		
		return True, isUpdate, gameId
		
				
	def useSingleScrapers(self, result, romCollection, startIndex, gamenameFromFile, foldername, firstRomfile, fuzzyFactor, updateOption, gui, progDialogRCHeader, fileCount):
		
		filecrc = ''
		artScrapers = {}
		
		for i in range(startIndex, len(romCollection.scraperSites)):
			scraperSite = romCollection.scraperSites[i]			
			
			gui.writeMsg(progDialogRCHeader, "Import game: " +gamenameFromFile, scraperSite.name + " - downloading info", fileCount)
			Logutil.log('using scraper: ' +scraperSite.name, util.LOG_LEVEL_INFO)
			
			if(scraperSite.searchGameByCRC and filecrc == ''):
				filecrc = self.getFileCRC(firstRomfile)
			
			urlsFromPreviousScrapers = []
			doContinue = False
			for scraper in scraperSite.scrapers:
				pyScraper = PyScraper()
				result, urlsFromPreviousScrapers, doContinue = pyScraper.scrapeResults(result, scraper, urlsFromPreviousScrapers, gamenameFromFile, foldername, filecrc, firstRomfile, fuzzyFactor, updateOption)
			if(doContinue):
				continue
									
			#Find Filetypes and Scrapers for Art Download
			if(len(result) > 0):
				for path in romCollection.mediaPaths:
					thumbKey = 'Filetype' + path.fileType.name 
					if(len(self.resolveParseResult(result, thumbKey)) > 0):
						if((thumbKey in artScrapers) == 0):
							artScrapers[thumbKey] = scraperSite.name
						
		return result, artScrapers
				
				
	def insertGameFromDesc(self, gamedescription, gamename, romCollection, filenamelist, foldername, isUpdate, gameId, gui, dialogDict=''):								
		if(gamedescription != None):
			game = self.resolveParseResult(gamedescription, 'Game')
		else:
			self.missingDescFile.write('%s\n' %gamename)
			
			ignoreGameWithoutDesc = self.Settings.getSetting(util.SETTING_RCB_IGNOREGAMEWITHOUTDESC).upper() == 'TRUE'
			if(ignoreGameWithoutDesc):
				Logutil.log('No description found for game "%s". Game will not be imported.' %gamename, util.LOG_LEVEL_WARNING)
				return None
			game = ''
			gamedescription = {}
					
		gameId, continueUpdate = self.insertData(gamedescription, gamename, romCollection, filenamelist, foldername, isUpdate, gameId, gui, dialogDict)
		return gameId, continueUpdate
	
	
			
	def insertData(self, gamedescription, gamenameFromFile, romCollection, romFiles, foldername, isUpdate, gameId, gui, dialogDict=''):
		Logutil.log("Insert data", util.LOG_LEVEL_INFO)
		
		publisher = self.resolveParseResult(gamedescription, 'Publisher')
		developer = self.resolveParseResult(gamedescription, 'Developer')
		year = self.resolveParseResult(gamedescription, 'ReleaseYear')
		
		yearId = self.insertForeignKeyItem(gamedescription, 'ReleaseYear', Year(self.gdb))
		genreIds = self.insertForeignKeyItemList(gamedescription, 'Genre', Genre(self.gdb))		
		publisherId = self.insertForeignKeyItem(gamedescription, 'Publisher', Publisher(self.gdb))
		developerId = self.insertForeignKeyItem(gamedescription, 'Developer', Developer(self.gdb))
		reviewerId = self.insertForeignKeyItem(gamedescription, 'Reviewer', Reviewer(self.gdb))	
		
		region = self.resolveParseResult(gamedescription, 'Region')		
		media = self.resolveParseResult(gamedescription, 'Media')
		controller = self.resolveParseResult(gamedescription, 'Controller')
		players = self.resolveParseResult(gamedescription, 'Players')		
		rating = self.resolveParseResult(gamedescription, 'Rating')
		votes = self.resolveParseResult(gamedescription, 'Votes')
		url = self.resolveParseResult(gamedescription, 'URL')
		perspective = self.resolveParseResult(gamedescription, 'Perspective')
		originalTitle = self.resolveParseResult(gamedescription, 'OriginalTitle')
		alternateTitle = self.resolveParseResult(gamedescription, 'AlternateTitle')
		translatedBy = self.resolveParseResult(gamedescription, 'TranslatedBy')
		version = self.resolveParseResult(gamedescription, 'Version')								
		plot = self.resolveParseResult(gamedescription, 'Description')
		
		if(gamedescription != None):
			gamename = self.resolveParseResult(gamedescription, 'Game')
			if(gamename != gamenameFromFile):
				self.possibleMismatchFile.write('%s, %s\n' %(gamename, gamenameFromFile))
			
			if(gamename == ""):
				gamename = gamenameFromFile
		else:
			gamename = gamenameFromFile
		
		artWorkFound = False
		artworkfiles = {}
		artworkurls = {}
		for path in romCollection.mediaPaths:
						
			Logutil.log("FileType: " +str(path.fileType.name), util.LOG_LEVEL_INFO)			
			
			#TODO replace %ROMCOLLECTION%, %PUBLISHER%, ... 
			fileName = path.path.replace("%GAME%", gamenameFromFile)
						
			continueUpdate, artworkurls = self.getThumbFromOnlineSource(gamedescription, path.fileType.name, fileName, gui, dialogDict, artworkurls)
			if(not continueUpdate):
				return None, False
			
			Logutil.log("Additional data path: " +str(path.path), util.LOG_LEVEL_DEBUG)
			files = self.resolvePath((path.path,), gamename, gamenameFromFile, foldername, romCollection.name, publisher, developer)
			if(len(files) > 0):
				artWorkFound = True
				
				#HACK: disable static image check as a preparation for new default image handling (this code has problems with [] in rom names)				
				"""
				imagePath = str(self.resolvePath((path.path,), gamename, gamenameFromFile, foldername, romCollection.name, publisher, developer))
				staticImageCheck = imagePath.upper().find(gamenameFromFile.upper())
				
				#make sure that it was no default image that was found here
				if(staticImageCheck != -1):
					artWorkFound = True
				"""					
			else:
				self.missingArtworkFile.write('%s (filename: %s) (%s)\n' %(gamename, gamenameFromFile, path.fileType.name))
			
			artworkfiles[path.fileType] = files
				
				
		if(not artWorkFound):
			ignoreGamesWithoutArtwork = self.Settings.getSetting(util.SETTING_RCB_IGNOREGAMEWITHOUTARTWORK).upper() == 'TRUE'
			if(ignoreGamesWithoutArtwork):								
				Logutil.log('No artwork found for game "%s". Game will not be imported.' %gamenameFromFile, util.LOG_LEVEL_WARNING)
				self.missingArtworkFile.write('--> No artwork found for game "%s". Game will not be imported.\n' %gamename)
				return None, True

			
		#create Nfo file with game properties
		createNfoFile = self.Settings.getSetting(util.SETTING_RCB_CREATENFOFILE).upper() == 'TRUE'	
		if(createNfoFile):
			self.createNfoFromDesc(gamename, plot, romCollection.name, publisher, developer, year, 
			players, rating, votes, url, region, media, perspective, controller, originalTitle, alternateTitle, version, gamedescription, romFiles[0], gamenameFromFile, artworkfiles, artworkurls)

						
		gameId = self.insertGame(gamename, plot, romCollection.id, publisherId, developerId, reviewerId, yearId, 
			players, rating, votes, url, region, media, perspective, controller, originalTitle, alternateTitle, translatedBy, version, isUpdate, gameId, romCollection.allowUpdate, )
		
		if(gameId == None):
			return None, True
						
		for genreId in genreIds:
			genreGame = GenreGame(self.gdb).getGenreGameByGenreIdAndGameId(genreId, gameId)
			if(genreGame == None):
				GenreGame(self.gdb).insert((genreId, gameId))
			
		for romFile in romFiles:
			fileType = FileType()
			fileType.id = 0
			fileType.name = "rcb_rom"
			fileType.parent = "game"
			self.insertFile(romFile, gameId, fileType, None, None, None)				
		
		Logutil.log("Importing files: " +str(artworkfiles), util.LOG_LEVEL_INFO)		
		for fileType in artworkfiles.keys():
			for fileName in artworkfiles[fileType]:
				self.insertFile(fileName, gameId, fileType, romCollection.id, publisherId, developerId)		
				
		self.gdb.commit()
		return gameId, True
		
		
	def insertGame(self, gameName, description, romCollectionId, publisherId, developerId, reviewerId, yearId, 
				players, rating, votes, url, region, media, perspective, controller, originalTitle, alternateTitle, translatedBy, version, isUpdate, gameId, allowUpdate):		
		
		try:
			if(not isUpdate):
				Logutil.log("Game does not exist in database. Insert game: " +gameName, util.LOG_LEVEL_INFO)
				Game(self.gdb).insert((gameName, description, None, None, romCollectionId, publisherId, developerId, reviewerId, yearId, 
					players, rating, votes, url, region, media, perspective, controller, 0, 0, originalTitle, alternateTitle, translatedBy, version))
				return self.gdb.cursor.lastrowid
			else:	
				if(allowUpdate):
					#TODO
					gameRow = None
					Logutil.log("Game does exist in database. Update game: " +gameName, util.LOG_LEVEL_INFO)
					Game(self.gdb).update(('name', 'description', 'romCollectionId', 'publisherId', 'developerId', 'reviewerId', 'yearId', 'maxPlayers', 'rating', 'numVotes',
						'url', 'region', 'media', 'perspective', 'controllerType', 'originalTitle', 'alternateTitle', 'translatedBy', 'version'),
						(gameName, description, romCollectionId, publisherId, developerId, reviewerId, yearId, players, rating, votes, url, region, media, perspective, controller,
						originalTitle, alternateTitle, translatedBy, version),
						gameId)
				else:
					Logutil.log("Game does exist in database but update is not allowed for current rom collection. game: " +gameName, util.LOG_LEVEL_INFO)
				
				return gameId
		except Exception, (exc):
			Logutil.log("An error occured while adding game '%s'. Error: %s" %(gameName, str(exc)), util.LOG_LEVEL_INFO)
			return None
			
		
	
	def insertForeignKeyItem(self, result, itemName, gdbObject):
		
		item = self.resolveParseResult(result, itemName)
						
		if(item != "" and item != None):
			itemRow = gdbObject.getOneByName(item)
			if(itemRow == None):	
				try:
					Logutil.log(itemName +" does not exist in database. Insert: " +item, util.LOG_LEVEL_INFO)
				except:
					pass
				gdbObject.insert((item,))
				itemId = self.gdb.cursor.lastrowid
			else:
				itemId = itemRow[0]
		else:
			itemId = None
			
		return itemId
		
	
	def insertForeignKeyItemList(self, result, itemName, gdbObject):
		idList = []				
				
		try:
			itemList = result[itemName]
			Logutil.log("Result " +itemName +" = " +str(itemList), util.LOG_LEVEL_INFO)
		except:
			Logutil.log("Error while resolving item: " +itemName, util.LOG_LEVEL_WARNING)
			return idList				
		
		for item in itemList:
			item = self.stripHTMLTags(item)
			
			itemRow = gdbObject.getOneByName(item)
			if(itemRow == None):
				try:
					Logutil.log(itemName +" does not exist in database. Insert: " +item, util.LOG_LEVEL_INFO)
				except:
					pass
				gdbObject.insert((item,))
				idList.append(self.gdb.cursor.lastrowid)
			else:
				idList.append(itemRow[0])
				
		return idList
		
		
	def resolvePath(self, paths, gamename, gamenameFromFile, foldername, romCollectionName, publisher, developer):		
		resolvedFiles = []				
				
		for path in paths:
			files = []
			Logutil.log("resolve path: " +path, util.LOG_LEVEL_INFO)
			
			if(path.find("%GAME%") > -1):
				
				pathnameFromFile = path.replace("%GAME%", gamenameFromFile)									
				Logutil.log("resolved path from rom file name: " +pathnameFromFile, util.LOG_LEVEL_INFO)					
				files = self.getFilesByWildcard(pathnameFromFile)
				if(len(files) == 0):
					files = self.getFilesByGameNameIgnoreCase(pathnameFromFile)
				
				if(gamename != gamenameFromFile and len(files) == 0):
					pathnameFromGameName = path.replace("%GAME%", gamename)
					Logutil.log("resolved path from game name: " +pathnameFromGameName, util.LOG_LEVEL_INFO)				
					files = self.getFilesByWildcard(pathnameFromGameName)
					if(len(files) == 0):
						files = self.getFilesByGameNameIgnoreCase(pathnameFromGameName)								
									
				if(gamename != foldername and len(files) == 0):
					pathnameFromFolder = path.replace("%GAME%", foldername)					
					Logutil.log("resolved path from rom folder name: " +pathnameFromFolder, util.LOG_LEVEL_INFO)					
					files = self.getFilesByWildcard(pathnameFromFolder)
					if(len(files) == 0):
						files = self.getFilesByGameNameIgnoreCase(pathnameFromFolder)								
				
							
				
				
				
			#TODO could be done only once per RomCollection
			if(path.find("%ROMCOLLECTION%") > -1 and romCollectionName != None and len(files) == 0):
				pathnameFromRomCollection = path.replace("%ROMCOLLECTION%", romCollectionName)
				Logutil.log("resolved path from rom collection name: " +pathnameFromRomCollection, util.LOG_LEVEL_INFO)
				files = self.getFilesByWildcard(pathnameFromRomCollection)				
				
			if(path.find("%PUBLISHER%") > -1 and publisher != None and len(files) == 0):
				pathnameFromPublisher = path.replace("%PUBLISHER%", publisher)
				Logutil.log("resolved path from publisher name: " +pathnameFromPublisher, util.LOG_LEVEL_INFO)
				files = self.getFilesByWildcard(pathnameFromPublisher)				
				
			if(path.find("%DEVELOPER%") > -1 and developer != None and len(files) == 0):
				pathnameFromDeveloper = path.replace("%DEVELOPER%", developer)
				Logutil.log("resolved path from developer name: " +pathnameFromDeveloper, util.LOG_LEVEL_INFO)
				files = self.getFilesByWildcard(pathnameFromDeveloper)													
			
			if(path.find("%GAME%") == -1 & path.find("%ROMCOLLECTION%") == -1 & path.find("%PUBLISHER%") == -1 & path.find("%DEVELOPER%") == -1):
				pathnameFromStaticFile = path
				Logutil.log("using static defined media file from path: " + pathnameFromStaticFile, util.LOG_LEVEL_INFO)
				files = self.getFilesByWildcard(pathnameFromStaticFile)			
				
			if(len(files) == 0):
				Logutil.log('No files found for game "%s" at path "%s". Make sure that file names are matching.' %(gamename, path), util.LOG_LEVEL_WARNING)
			for file in files:
				if(os.path.exists(file)):
					resolvedFiles.append(file)
					
		return resolvedFiles
	
	
	def getFilesByWildcard(self, pathName):
		
		files = []
		
		try:
			# try glob with * wildcard
			files = glob.glob(pathName)
		except Exception, (exc):
			Logutil.log("Error using glob function in resolvePath " +str(exc), util.LOG_LEVEL_WARNING)
			
		if(len(files) == 0):				
			#HACK: removed \s from regular expression. previous version was '\s\[.*\]' 
			squares = re.findall('\[.*\]',pathName)
			if(squares != None and len(squares) >= 1):
				Logutil.log('Replacing [...] with *', util.LOG_LEVEL_INFO)
				for square in squares:						
					pathName = pathName.replace(square, '*')
			
				Logutil.log('new pathname: ' +str(pathName), util.LOG_LEVEL_INFO)
				try:
					files = glob.glob(pathName)
				except Exception, (exc):
					Logutil.log("Error using glob function in resolvePath " +str(exc), util.LOG_LEVEL_WARNING)
		
		# glob can't handle []-characters - try it with listdir
		if(len(files)  == 0):
			try:				
				if(os.path.isfile(pathName)):
					files.append(pathName)
				else:
					files = os.listdir(pathName)					
			except:
				pass
		Logutil.log("resolved files: " +str(files), util.LOG_LEVEL_INFO)
		return files		
		
		
	def getFilesByGameNameIgnoreCase(self, pathname):
		
		files = []
		
		dirname = os.path.dirname(pathname)
		basename = os.path.basename(pathname)
		
		#search all Files that start with the first character of game name
		newpath = os.path.join(dirname, basename[0].upper() +'*')
		filesUpper = glob.glob(newpath)
		newpath = os.path.join(dirname, basename[0].lower() +'*')
		filesLower = glob.glob(newpath)
		
		allFiles = filesUpper + filesLower
		for file in allFiles:
			if(pathname.lower() == file.lower()):
				Logutil.log('Found path "%s" by search with ignore case.' %pathname, util.LOG_LEVEL_WARNING)
				files.append(file)
				
		return files
		
		
	def resolveParseResult(self, result, itemName):
		
		resultValue = ""
		
		try:			
			resultValue = result[itemName][0]
			
			if(itemName == 'ReleaseYear' and resultValue != None):
				if(type(resultValue) is time.struct_time):
					resultValue = str(resultValue[0])
				elif(len(resultValue) > 4):
					resultValueOrig = resultValue
					resultValue = resultValue[0:4]
					try:
						#year must be numeric
						int(resultValue)
					except:
						resultValue = resultValueOrig[len(resultValueOrig) -4:]
						try:
							int(resultValue)
						except:
							resultValue = ''
							
			#replace and remove HTML tags
			resultValue = self.stripHTMLTags(resultValue)
			resultValue = resultValue.strip()
									
		except Exception, (exc):
			Logutil.log("Error while resolving item: " +itemName +" : " +str(exc), util.LOG_LEVEL_WARNING)
						
		try:
			Logutil.log("Result " +itemName +" = " +resultValue, util.LOG_LEVEL_DEBUG)
		except:
			pass
				
		return resultValue
	
	
	def stripHTMLTags(self, inputString):
				
		inputString = util.html_unescape(inputString)
		
		#remove html tags and double spaces
		intag = [False]
		lastSpace = [False]
		def chk(c):
			if intag[0]:
				intag[0] = (c != '>')
				lastSpace[0] = (c == ' ')
				return False
			elif c == '<':
				intag[0] = True
				lastSpace[0] = (c == ' ')
				return False
			if(c == ' ' and lastSpace[0]):
				lastSpace[0] = (c == ' ')
				return False
			lastSpace[0] = (c == ' ')
			return True
		
		return ''.join(c for c in inputString if chk(c))


	def createNfoFromDesc(self, gamename, plot, romCollectionName, publisher, developer, year, players, rating, votes, 
						url, region, media, perspective, controller, originalTitle, alternateTitle, version, gamedescription, romFile, gameNameFromFile, artworkfiles, artworkurls):
		
		root = Element('game')
		SubElement(root, 'title').text = gamename		
		SubElement(root, 'originalTitle').text = originalTitle
		SubElement(root, 'alternateTitle').text = alternateTitle
		SubElement(root, 'platform').text = romCollectionName
		SubElement(root, 'plot').text = plot
		SubElement(root, 'publisher').text = publisher
		SubElement(root, 'developer').text = developer
		SubElement(root, 'year').text = year
				
		try:
			genreList = gamedescription['Genre']			
		except:
			genreList = []
		
		for genre in genreList:
			SubElement(root, 'genre').text = str(genre)
		
		SubElement(root, 'detailUrl').text = url
		SubElement(root, 'maxPlayer').text = players
		SubElement(root, 'region').text = region
		SubElement(root, 'media').text = media
		SubElement(root, 'perspective').text = perspective
		SubElement(root, 'controller').text = controller
		SubElement(root, 'version').text = version
		SubElement(root, 'rating').text = rating
		SubElement(root, 'votes').text = votes
		
		for artworktype in artworkfiles.keys():
			
			local = ''
			online = ''
			try:
				local = artworkfiles[artworktype][0]
				online = str(artworkurls[artworktype.name])
			except:
				pass
			
			try:
				SubElement(root, 'thumb', {'type' : artworktype.name, 'local' : local}).text = online
			except Exception, (exc):
				print 'Error writing artwork url: ' +str(exc)
				pass
		
		#write file		
		try:
			util.indentXml(root)
			tree = ElementTree(root)
			
			romDir = os.path.dirname(romFile)
			Logutil.log('Romdir: ' +str(romDir), util.LOG_LEVEL_INFO)
			nfoFile = os.path.join(romDir, gameNameFromFile +'.nfo')
			
			if (not os.path.isfile(nfoFile)):
				Logutil.log('Writing NfoFile: ' +str(nfoFile), util.LOG_LEVEL_INFO)
			else:
				Logutil.log('NfoFile already exists. Wont overwrite file: ' +str(nfoFile), util.LOG_LEVEL_INFO)
				return
												
			tree.write(nfoFile)
			
		except Exception, (exc):
			print("Error: Cannot write game.nfo: " +str(exc))		
			
		
	def insertFile(self, fileName, gameId, fileType, romCollectionId, publisherId, developerId):
		Logutil.log("Begin Insert file: " +fileName, util.LOG_LEVEL_DEBUG)										
		
		parentId = None
		
		#TODO console and romcollection could be done only once per RomCollection			
		#fileTypeRow[3] = parent
		if(fileType.parent == 'game'):
			Logutil.log("Insert file with parent game", util.LOG_LEVEL_INFO)
			parentId = gameId
		elif(fileType.parent == 'romcollection'):
			Logutil.log("Insert file with parent romcollection.", util.LOG_LEVEL_INFO)
			parentId = romCollectionId		
		elif(fileType.parent == 'publisher'):
			Logutil.log("Insert file with parent publisher", util.LOG_LEVEL_INFO)
			parentId = publisherId
		elif(fileType.parent == 'developer'):
			Logutil.log("Insert file with parent developer", util.LOG_LEVEL_INFO)
			parentId = developerId
					
		Logutil.log("Insert file with parentid: " +str(parentId), util.LOG_LEVEL_INFO)
			
		fileRow = File(self.gdb).getFileByNameAndTypeAndParent(fileName, fileType.id, parentId)
		if(fileRow == None):
			Logutil.log("File does not exist in database. Insert file: " +fileName, util.LOG_LEVEL_INFO)
			File(self.gdb).insert((str(fileName), fileType.id, parentId))
				
	
	def getThumbFromOnlineSource(self, gamedescription, fileType, fileName, gui, dialogDict, artworkurls):
		Logutil.log("Get thumb from online source", util.LOG_LEVEL_INFO)
		try:
			#maybe we got a thumb url from desc parser
			thumbKey = 'Filetype' +fileType
			Logutil.log("using key: " +thumbKey, util.LOG_LEVEL_INFO)
			thumbUrl = self.resolveParseResult(gamedescription, thumbKey)
			if(thumbUrl == ''):
				return True, artworkurls
			
			artworkurls[fileType] = thumbUrl
			
			Logutil.log("Get thumb from url: " +str(thumbUrl), util.LOG_LEVEL_INFO)
			
			rootExtFile = os.path.splitext(fileName)
			rootExtUrl = os.path.splitext(thumbUrl)
			
			if(len(rootExtUrl) == 2 and len(rootExtFile) != 0):
				fileName = rootExtFile[0] + rootExtUrl[1]
				gameName = rootExtFile[0] + ".*"
				files = self.getFilesByWildcard(gameName)
			
			#check if folder exists
			dirname = os.path.dirname(fileName)
			if(not os.path.isdir(dirname)):
				try:
					os.mkdir(dirname)
				except Exception, (exc):
					xbmcgui.Dialog().ok('Error: Could not create artwork directory.', 'Check xbmc.log for details.')
					Logutil.log("Could not create directory: '%s'. Error message: '%s'" %(dirname, str(exc)), util.LOG_LEVEL_ERROR)
					return False, artworkurls
				
			
			Logutil.log("Download file to: " +str(fileName), util.LOG_LEVEL_INFO)			
			if(len(files) == 0):
				Logutil.log("File does not exist. Starting download.", util.LOG_LEVEL_INFO)
				
				#Dialog Status Art Download
				try:
					if(dialogDict != ''):
						progDialogRCHeader = dialogDict["dialogHeaderKey"]
						gamenameFromFile = dialogDict["gameNameKey"]
						scraperSiteName = dialogDict["scraperSiteKey"]
						fileCount = dialogDict["fileCountKey"]
						gui.writeMsg(progDialogRCHeader, "Import game: " +gamenameFromFile, str(scraperSiteName[thumbKey]) + " - downloading art", fileCount)
				except:
					pass

				# fetch thumbnail and save to filepath
				try:
					urllib.urlretrieve( thumbUrl, str(fileName))
				except Exception, (exc):
					xbmcgui.Dialog().ok('Error: Could not create artwork file.', 'Check xbmc.log for details.')
					Logutil.log("Could not create file: '%s'. Error message: '%s'" %(str(fileName), str(exc)), util.LOG_LEVEL_ERROR)
					return False, artworkurls
				
				# cleanup any remaining urllib cache
				urllib.urlcleanup()
				Logutil.log("Download finished.", util.LOG_LEVEL_INFO)
			else:
				Logutil.log("File already exists. Won't download again.", util.LOG_LEVEL_INFO)
		except Exception, (exc):
			Logutil.log("Error in getThumbFromOnlineSource: " +str(exc), util.LOG_LEVEL_WARNING)						

		return True, artworkurls


	def openFile(self, filename):
		try:			
			filehandle = open(filename,'w')		
		except Exception, (exc):			
			Logutil.log('Cannot write to file "%s". Error: "%s"' %(filename, str(exc)), util.LOG_LEVEL_WARNING)
			return None
		
		return filehandle
		

	def exit(self):
		
		try:
			self.missingArtworkFile.close()
			self.missingDescFile.close()
		except:
			pass
		
		Logutil.log("Update finished", util.LOG_LEVEL_INFO)		