# -*- coding: utf-8 -*-
"""
DreamPlex Plugin by DonDavici, 2012
and jbleyel 2021

Original -> https://github.com/oe-alliance/DreamPlex
Fork -> https://github.com/oe-alliance/DreamPlex

Some of the code is from other plugins:
all credits to the coders :-)

DreamPlex Plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

DreamPlex Plugin is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
"""
#===============================================================================
# IMPORT
#===============================================================================
from os import environ, listdir
from os.path import isdir, join as path_join, isfile
import gettext

from Components.config import config
from Components.config import ConfigSubsection
from Components.config import ConfigSelection
from Components.config import ConfigInteger
from Components.config import ConfigSubList
from Components.config import ConfigText
from Components.config import ConfigYesNo
from Components.config import ConfigIP
from Components.config import ConfigPIN
from Components.config import ConfigDirectory
from Components.Language import language

from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_SKIN, SCOPE_CURRENT_SKIN, SCOPE_LANGUAGE


from .DPH_Singleton import Singleton
from .DP_ViewFactory import getViews

from .__common__ import getVersion, registerPlexFonts, loadSkinParams, loadPlexSkin, checkPlexEnvironment, getBoxInformation, printl2 as printl, getXmlContent, getBoxResolution, getSkinFolder, setSkinFolder, getSkinResolution

#===============================================================================
#
#===============================================================================
version = getVersion()
source = "ipk"  # other option is "ipk"

defaultPluginFolderPath = resolveFilename(SCOPE_PLUGINS, "Extensions/DreamFin/")
defaultSkinsFolderPath = resolveFilename(SCOPE_PLUGINS, "Extensions/DreamFin/skins")
defaultLogFolderPath = "/tmp/"
defaultCacheFolderPath = "/hdd/dreamfin/cache/"
defaultMediaFolderPath = "/hdd/dreamfin/media/"
defaultPlayerTempPath = "/hdd/dreamfin/"
defaultConfigFolderPath = "/hdd/dreamfin/config/"

# skin data
defaultSkin = "original"
skins = []

config.plugins.dreamfin = ConfigSubsection()
config.plugins.dreamfin.about = ConfigSelection(default="1", choices=[("1", " ")])  # need this for seperator in settings
config.plugins.dreamfin.debugMode = ConfigYesNo()
config.plugins.dreamfin.writeDebugFile = ConfigYesNo()
config.plugins.dreamfin.showInMainMenu = ConfigYesNo(default=True)
config.plugins.dreamfin.showFilter = ConfigYesNo(default=True)
config.plugins.dreamfin.autoLanguage = ConfigYesNo()
config.plugins.dreamfin.playTheme = ConfigYesNo()
config.plugins.dreamfin.showUnSeenCounts = ConfigYesNo()
config.plugins.dreamfin.fastScroll = ConfigYesNo()
config.plugins.dreamfin.liveTvInViews = ConfigYesNo()
config.plugins.dreamfin.startWithFilterMode = ConfigYesNo()
config.plugins.dreamfin.summerizeSections = ConfigYesNo(default=True)
config.plugins.dreamfin.summerizeServers = ConfigYesNo(default=True)
config.plugins.dreamfin.stopLiveTvOnStartup = ConfigYesNo()
# both caches default off: against remote HTTPS servers the on-disk cache
# is more trouble than it is worth (and needs a real /hdd mount, which the
# box may not have - a missing mount left 0-byte poster files)
config.plugins.dreamfin.useCache = ConfigYesNo(default=False)
config.plugins.dreamfin.usePicCache = ConfigYesNo(default=False)
config.plugins.dreamfin.useBackdropVideos = ConfigYesNo()
config.plugins.dreamfin.showDetailsInList = ConfigYesNo()
config.plugins.dreamfin.showDetailsInListDetailType = ConfigSelection(default="1", choices=[("1", "user"), ("2", "server")])
config.plugins.dreamfin.boxName = ConfigText(default="DreamFin", visible_width=50, fixed_size=False)
config.plugins.dreamfin.lcd4linux = ConfigYesNo()
config.plugins.dreamfin.exitFunction = ConfigSelection(default="0", choices=[("0", "Nothing"), ("1", "stop playback, return to library"), ("2", "search library while playing")])

config.plugins.dreamfin.pluginfolderpath = ConfigDirectory(default=defaultPluginFolderPath)
config.plugins.dreamfin.skinfolderpath = ConfigDirectory(default=defaultSkinsFolderPath)

config.plugins.dreamfin.seekTime = ConfigInteger(default=5, limits=(1, 30))

# accent color of the last entered server; decides which skin variant the
# next plugin start loads (jellyfin lilac is the fresh-install default)
config.plugins.dreamfin.lastAccent = ConfigSelection(default="jellyfin", choices=[("emby", "Emby"), ("jellyfin", "Jellyfin")])

config.plugins.dreamfin.logfolderpath = ConfigDirectory(default=defaultLogFolderPath, visible_width=50)
config.plugins.dreamfin.cachefolderpath = ConfigDirectory(default=defaultCacheFolderPath, visible_width=50)
config.plugins.dreamfin.mediafolderpath = ConfigDirectory(default=defaultMediaFolderPath, visible_width=50)
config.plugins.dreamfin.configfolderpath = ConfigDirectory(default=defaultConfigFolderPath, visible_width=50)
config.plugins.dreamfin.playerTempPath = ConfigDirectory(default=defaultPlayerTempPath, visible_width=50)

config.plugins.dreamfin.entriescount = ConfigInteger(0)
config.plugins.dreamfin.Entries = ConfigSubList()

#===============================================================================
#
#===============================================================================


def initBoxInformation():
	printl("", "__init__::getBoxInformation", "S")

	boxInfo = getBoxInformation()
	printl("=== BOX INFORMATION ===", "__init__::getBoxInformation", "I")
	printl("Box: " + str(boxInfo), "__init__::getBoxInformation", "I")

	printl("", "__init__::getBoxInformation", "C")

#===============================================================================
#
#===============================================================================


def printGlobalSettings():
	printl("", "__init__::initGlobalSettings", "S")

	printl("=== VERSION ===", "__init__::getBoxInformation", "I")
	printl("current Version : " + str(version), "__init__::initGlobalSettings", "I")

	printl("=== GLOBAL SETTINGS ===", "__init__::getBoxInformation", "I")
	printl("debugMode: " + str(config.plugins.dreamfin.debugMode.value), "__init__::initGlobalSettings", "I")
	printl("writeDebugFile: " + str(config.plugins.dreamfin.writeDebugFile.value), "__init__::initGlobalSettings", "I")
	printl("boxName: " + str(config.plugins.dreamfin.boxName.value), "__init__::initGlobalSettings", "I")
	printl("pluginfolderpath: " + str(config.plugins.dreamfin.pluginfolderpath.value), "__init__::initGlobalSettings", "I")
	printl("logfolderpath: " + str(config.plugins.dreamfin.logfolderpath.value), "__init__::initGlobalSettings", "I")
	printl("mediafolderpath: " + str(config.plugins.dreamfin.mediafolderpath.value), "__init__::initGlobalSettings", "I")
	printl("cachefolderpath: " + str(config.plugins.dreamfin.cachefolderpath.value), "__init__::initGlobalSettings", "I")
	printl("playerTempPath: " + str(config.plugins.dreamfin.playerTempPath.value), "__init__::initGlobalSettings", "I")
	printl("showInMainMenu: " + str(config.plugins.dreamfin.showInMainMenu.value), "__init__::initGlobalSettings", "I")
	printl("showFilter: " + str(config.plugins.dreamfin.showFilter.value), "__init__::initGlobalSettings", "I")
	printl("autoLanguage: " + str(config.plugins.dreamfin.autoLanguage.value), "__init__::initGlobalSettings", "I")
	printl("stopLiveTvOnStartup: " + str(config.plugins.dreamfin.stopLiveTvOnStartup.value), "__init__::initGlobalSettings", "I")
	printl("playTheme: " + str(config.plugins.dreamfin.playTheme.value), "__init__::initGlobalSettings", "I")
	printl("fastScroll: " + str(config.plugins.dreamfin.fastScroll.value), "__init__::initGlobalSettings", "I")
	printl("summerizeSections: " + str(config.plugins.dreamfin.summerizeSections.value), "__init__::initGlobalSettings", "I")
	printl("summerizeServers: " + str(config.plugins.dreamfin.summerizeServers.value), "__init__::initGlobalSettings", "I")
	printl("useCache: " + str(config.plugins.dreamfin.useCache.value), "__init__::initGlobalSettings", "I")
	printl("usePicCache: " + str(config.plugins.dreamfin.usePicCache.value), "__init__::initGlobalSettings", "I")

	printl("", "__init__::initPlexSettings", "C")

#===============================================================================
#
#===============================================================================


def initServerEntryConfig():
	printl("", "__init__::initServerEntryConfig", "S")

	config.plugins.dreamfin.Entries.append(ConfigSubsection())
	i = len(config.plugins.dreamfin.Entries) - 1

	defaultName = "MediaServer"
	defaultIp = [192, 168, 0, 1]
	defaultPort = 8096

	# SERVER SETTINGS
	config.plugins.dreamfin.Entries[i].id = ConfigInteger(i)
	config.plugins.dreamfin.Entries[i].state = ConfigYesNo(default=True)
	config.plugins.dreamfin.Entries[i].autostart = ConfigYesNo()
	config.plugins.dreamfin.Entries[i].name = ConfigText(default=defaultName, visible_width=50, fixed_size=False)
	config.plugins.dreamfin.Entries[i].connectionType = ConfigSelection(default="1", choices=[("0", _("IP")), ("1", _("DNS"))])
	config.plugins.dreamfin.Entries[i].ip = ConfigIP(default=defaultIp)
	config.plugins.dreamfin.Entries[i].dns = ConfigText(default="my.dns.url", visible_width=50, fixed_size=False)
	config.plugins.dreamfin.Entries[i].port = ConfigInteger(default=defaultPort, limits=(1, 65555))
	config.plugins.dreamfin.Entries[i].playbackType = ConfigSelection(default="0", choices=[("0", _("Streamed")), ("1", _("Transcoded")), ("2", _("Direct Local"))])
	config.plugins.dreamfin.Entries[i].loadExtraData = ConfigSelection(default="0", choices=[("0", "None"), ("1", "Server"), ("2", "YTTrailer")])

	# EMBY/JELLYFIN
	config.plugins.dreamfin.Entries[i].serverType = ConfigSelection(default="auto", choices=[("auto", _("Auto")), ("emby", "Emby"), ("jellyfin", "Jellyfin")])
	config.plugins.dreamfin.Entries[i].username = ConfigText(visible_width=50, fixed_size=False)
	config.plugins.dreamfin.Entries[i].password = ConfigText(visible_width=50, fixed_size=False)
	# manually entered API key, wins over username/password
	config.plugins.dreamfin.Entries[i].accessToken = ConfigText(visible_width=50, fixed_size=False)
	# session token + user id cached from the last successful login
	config.plugins.dreamfin.Entries[i].accessTokenCache = ConfigText(visible_width=50, fixed_size=False)
	config.plugins.dreamfin.Entries[i].userIdCache = ConfigText(visible_width=50, fixed_size=False)

	config.plugins.dreamfin.Entries[i].srtRenamingForDirectLocal = ConfigYesNo()
	config.plugins.dreamfin.Entries[i].subtitlesLanguage = ConfigText(default="de", visible_width=10, fixed_size=False)
	config.plugins.dreamfin.Entries[i].useForcedSubtitles = ConfigYesNo(default=True)

	printl("=== SERVER SETTINGS ===", "__init__::initServerEntryConfig", "D")
	printl("Server Settings: ", "__init__::initServerEntryConfig", "D")
	printl("id: " + str(config.plugins.dreamfin.Entries[i].id.value), "__init__::initServerEntryConfig", "D")
	printl("state: " + str(config.plugins.dreamfin.Entries[i].state.value), "__init__::initServerEntryConfig", "D")
	printl("autostart: " + str(config.plugins.dreamfin.Entries[i].autostart.value), "__init__::initServerEntryConfig", "D")
	printl("name: " + str(config.plugins.dreamfin.Entries[i].name.value), "__init__::initServerEntryConfig", "D")
	printl("connectionType: " + str(config.plugins.dreamfin.Entries[i].connectionType.value), "__init__::initServerEntryConfig", "D")
	printl("ip: " + str(config.plugins.dreamfin.Entries[i].ip.value), "__init__::initServerEntryConfig", "D")
	printl("dns: " + str(config.plugins.dreamfin.Entries[i].dns.value), "__init__::initServerEntryConfig", "D")
	printl("port: " + str(config.plugins.dreamfin.Entries[i].port.value), "__init__::initServerEntryConfig", "D")
	printl("playbackType: " + str(config.plugins.dreamfin.Entries[i].playbackType.value), "__init__::initServerEntryConfig", "D")

	# STREAMED
	# no options at the moment

	# TRANSCODED
	config.plugins.dreamfin.Entries[i].universalTranscoder = ConfigYesNo(default=True)

	# old transcoder settings
	config.plugins.dreamfin.Entries[i].quality = ConfigSelection(default="7", choices=[("0", _("64kbps, 128p, 3fps")), ("1", _("96kbps, 128p, 12fps")), ("2", _("208kbps, 160p, 15fps")), ("3", _("320kbps, 240p")), ("4", _("720kbps, 320p")), ("5", _("1.5Mbps, 480p")), ("6", _("2Mbps, 720p")), ("7", _("3Mbps, 720p")), ("8", _("4Mbps, 720p")), ("9", _("8Mbps, 1080p")), ("10", _("10Mbps, 1080p")), ("11", _("12Mbps, 1080p")), ("12", _("20Mbps, 1080p"))])
	config.plugins.dreamfin.Entries[i].segments = ConfigInteger(default=5, limits=(1, 10))

	# universal transcoder settings
	config.plugins.dreamfin.Entries[i].uniQuality = ConfigSelection(default="3", choices=[("0", _("420x240, 320kbps")), ("1", _("576x320, 720 kbps")), ("2", _("720x480, 1,5mbps")), ("3", _("1024x768, 2mbps")), ("4", _("1280x720, 3mbps")), ("5", _("1280x720, 4mbps")), ("6", _("1920x1080, 8mbps")), ("7", _("1920x1080, 10mbps")), ("8", _("1920x1080, 12mbps")), ("9", _("1920x1080, 20mbps"))])
	# progressive .ts fallback for gstreamer builds whose hlsdemux chokes on
	# the transcode m3u8 (the phase-4 OpenATV 6.4 gate); off = HLS master
	config.plugins.dreamfin.Entries[i].progressiveTranscode = ConfigYesNo(default=False)
	# transcode target video codec: h264 for max compatibility (older gstreamer
	# / OpenATV 6.4), hevc for better quality at a lower bitrate on boxes that
	# decode HEVC (e.g. the SF8008); the server still needs the HEVC encoder
	config.plugins.dreamfin.Entries[i].transcodeVideoCodec = ConfigSelection(default="h264", choices=[("h264", "H.264"), ("hevc", _("HEVC (H.265)"))])

	printl("=== TRANSCODED ===", "__init__::initServerEntryConfig", "D")
	printl("universalTranscoder: " + str(config.plugins.dreamfin.Entries[i].universalTranscoder.value), "__init__::initServerEntryConfig", "D")
	printl("quality: " + str(config.plugins.dreamfin.Entries[i].quality.value), "__init__::initServerEntryConfig", "D")
	printl("segments: " + str(config.plugins.dreamfin.Entries[i].segments.value), "__init__::initServerEntryConfig", "D")
	printl("uniQuality: " + str(config.plugins.dreamfin.Entries[i].uniQuality.value), "__init__::initServerEntryConfig", "D")
	# TRANSCODED VIA PROXY

	# DIRECT LOCAL
	printl("=== DIRECT LOCAL ===", "__init__::initServerEntryConfig", "D")
	printl("use forced subtitles: " + str(config.plugins.dreamfin.Entries[i].useForcedSubtitles.value), "__init__::initServerEntryConfig", "D")

	# DIRECT REMOTE
	config.plugins.dreamfin.Entries[i].smbUser = ConfigText(visible_width=50, fixed_size=False)
	config.plugins.dreamfin.Entries[i].smbPassword = ConfigText(visible_width=50, fixed_size=False)
	config.plugins.dreamfin.Entries[i].nasOverrideIp = ConfigIP(default=[192, 168, 0, 1])
	config.plugins.dreamfin.Entries[i].nasRoot = ConfigText(default="/", visible_width=50, fixed_size=False)

	printl("=== DIRECT REMOTE ===", "__init__::initServerEntryConfig", "D")
	printl("smbUser: " + str(config.plugins.dreamfin.Entries[i].smbUser.value), "__init__::initServerEntryConfig", "D", True)
	printl("smbPassword: " + str(config.plugins.dreamfin.Entries[i].smbPassword.value), "__init__::initServerEntryConfig", "D", True)
	printl("nasOverrideIp: " + str(config.plugins.dreamfin.Entries[i].nasOverrideIp.value), "__init__::initServerEntryConfig", "D")
	printl("nasRoot: " + str(config.plugins.dreamfin.Entries[i].nasRoot.value), "__init__::initServerEntryConfig", "D")

	# WOL
	config.plugins.dreamfin.Entries[i].wol = ConfigYesNo()
	config.plugins.dreamfin.Entries[i].wol_mac = ConfigText(default="00AA00BB00CC", visible_width=12, fixed_size=False)
	config.plugins.dreamfin.Entries[i].wol_delay = ConfigInteger(default=60, limits=(1, 180))

	printl("=== WOL ===", "__init__::initServerEntryConfig", "D")
	printl("wol: " + str(config.plugins.dreamfin.Entries[i].wol.value), "__init__::initServerEntryConfig", "D")
	printl("wol_mac: " + str(config.plugins.dreamfin.Entries[i].wol_mac.value), "__init__::initServerEntryConfig", "D")
	printl("wol_delay: " + str(config.plugins.dreamfin.Entries[i].wol_delay.value), "__init__::initServerEntryConfig", "D")

	printl("", "__init__::initServerEntryConfig", "C")
	return config.plugins.dreamfin.Entries[i]

#===============================================================================
#
#===============================================================================


def registerSkinParamsInstance():
	printl("", "__init__::registerSkinParamsInstance", "S")

	boxResolution = str(getBoxResolution())
	skinName = str(config.plugins.dreamfin.skin.value)
	printl("current skin: " + skinName, "__common__::registerSkinParamsInstance", "S")

	# if we are our default we switch automatically between the resolutions
	if (skinName == "default" or skinName == "BlueMod") and boxResolution == "FHD":
		skinName = "%s_FHD" % skinName

	skinfolder = "/usr/lib/enigma2/python/Plugins/Extensions/DreamFin/skins/%s" % skinName

	setSkinFolder(currentSkinFolder=skinfolder)
	printl("current skinfolder: " + skinfolder, "__common__::checkSkinResolution", "S")

	configXml = getXmlContent(skinfolder + "/params")
	Singleton().getSkinParamsInstance(configXml)

	printl("", "__init__::registerSkinParamsInstance", "C")

#===============================================================================
#
#===============================================================================


def checkSkinResolution():
	printl("", "__init__::checkSkinResolution", "S")

	boxResolution = str(getBoxResolution())
	printl("boxResolution: " + boxResolution, "__common__::checkSkinResolution", "S")

	skinResolution = str(getSkinResolution())
	printl("skinResolution: " + skinResolution, "__common__::checkSkinResolution", "S")

	if boxResolution == "HD" and skinResolution == "FHD":
		# if there is setup another FHD skin but the box skin is HD we switch automatically to default HD skin to avoid wrong screen size
		# which leads to unconfigurable dreamplex
		skinfolder = "/usr/lib/enigma2/python/Plugins/Extensions/DreamFin/skins/default"
		printl("switching to default due to mismatch of box and skin resolution!")

		setSkinFolder(currentSkinFolder=skinfolder)
		printl("current skinfolder: " + skinfolder, "__common__::checkSkinResolution", "S")

		configXml = getXmlContent(skinfolder + "/params")
		Singleton().getSkinParamsInstance(configXml)

	printl("", "__init__::checkSkinResolution", "C")

#===============================================================================
#
#===============================================================================


def initPlexServerConfig():
	printl("", "__init__::initPlexServerConfig", "S")

	count = config.plugins.dreamfin.entriescount.value
	if count != 0:
		i = 0
		while i < count:
			initServerEntryConfig()
			i += 1

	printl("", "__init__::initPlexServerConfig", "C")

#===============================================================================
#
#===============================================================================


def loadPlexPlugins():
	printl("", "__init__::loadPlexPlugins", "S")

	# we have to load them here because they are not ready though
	from .DP_LibMovies import DP_LibMovies
	from .DP_LibShows import DP_LibShows
	from .DP_LibMusic import DP_LibMusic
	from .DP_LibMixed import DP_LibMixed
	from .__plugin__ import registerPlugin, Plugin

	printl("registering ... movies", "__init__::loadPlexPlugins", "D")
	registerPlugin(Plugin(pid="movies", name=_("Movies"), start=DP_LibMovies, where=Plugin.MENU_MOVIES))

	printl("registering ... tvshows", "__init__::loadPlexPlugins", "D")
	registerPlugin(Plugin(pid="tvshows", name=_("TV Shows"), start=DP_LibShows, where=Plugin.MENU_TVSHOWS))

	printl("registering ... music", "__init__::loadPlexPlugins", "D")
	registerPlugin(Plugin(pid="music", name=_("Music"), start=DP_LibMusic, where=Plugin.MENU_MUSIC))

	printl("registering ... mixed", "__init__::loadPlexPlugins", "D")
	registerPlugin(Plugin(pid="mixed", name=_("Mixed"), start=DP_LibMixed, where=Plugin.MENU_MIXED))

	#printl("registering ... pictures", "__initgetBoxInformationt__::loadPlexPlugins", "D")
	#registerPlugin(Plugin(pid="tvshows", name=_("Music"), start=DP_LibPictures, where=Plugin.MENU_PICTURES))

	#printl("registering ... channels", "__initgetBoxInformationt__::loadPlexPlugins", "D")
	#registerPlugin(Plugin(pid="tvshows", name=_("Music"), start=DP_LibChannels, where=Plugin.MENU_CHANNELS))

	printl("", "__init__::loadPlexPlugins", "C")


#===============================================================================
#
#===============================================================================
def localeInit():
	printl("", "__init__::localeInit", "S")

	lang = language.getLanguage()
	environ["LANGUAGE"] = lang[:2]
	gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
	gettext.textdomain("enigma2")
	gettext.bindtextdomain("DreamFin", "%s%s" % (resolveFilename(SCOPE_PLUGINS), "Extensions/DreamFin/locale/"))

	printl("", "__init__::localeInit", "C")

#===============================================================================
#
#===============================================================================


def getInstalledSkins():
	printl("", "__init__::getInstalledSkins", "S")

	mySkins = []
	myDefaultSkin = "default"

	try:
		folderpath = config.plugins.dreamfin.skinfolderpath.value
		for skin in listdir(folderpath):
			if skin not in ["default_FHD", "BlueMod_FHD"]:  # we exclude the default_FHD and BlueMod_FHD because we switch between HD and FHD automatically
				# print(("skin: " + str(skin), None, "D"))
				if isdir(path_join(folderpath, skin)):
					mySkins.append(skin)
	except Exception as ex:
		printl("no skin found in Dreamplex", "__init__::getInstalledSkins", "D")
		printl("Exception(" + str(type(ex)) + "): " + str(ex), "__init__::getInstalledSkins", "E")
		mySkins.append(myDefaultSkin)

	#Also check if a real enigma2 skin contains dreamplex screens
	try:
		skinPath = resolveFilename(SCOPE_SKIN)
		printl("__init__:: Current enigma2 skin " + resolveFilename(SCOPE_CURRENT_SKIN), "__init__::getInstalledSkins", "D")

		for skin in listdir(skinPath):
			path = path_join(skinPath, skin)
			if isdir(path):
				xml = path_join(path, "skin_dreamfin.xml")
				if isfile(xml):
					mySkins.append("~" + skin)
	except Exception as ex:
		printl("no skindata in enigma2 skin found", "__init__::getInstalledSkins", "D")
		printl("Exception(" + str(type(ex)) + "): " + str(ex), "__init__::getInstalledSkins", "E")

	printl("Found enigma2 skins \"%s\"" % str(mySkins), "__init__::getInstalledSkins", "D")

	config.plugins.dreamfin.skin = ConfigSelection(default=myDefaultSkin, choices=mySkins)

	printl("", "__init__::getInstalledSkins", "C")

#===============================================================================
#
#===============================================================================


def getViewTypesForSettings():
	printl("", "__init__::getViewTypesForSettings", "S")

	# view settings
	viewChoicesForMovies = getViewsByType("movies")
	config.plugins.dreamfin.defaultMovieView = ConfigSelection(default="0", choices=viewChoicesForMovies)

	viewChoicesForShows = getViewsByType("shows")
	config.plugins.dreamfin.defaultShowView = ConfigSelection(default="0", choices=viewChoicesForShows)

	viewChoicesForMusic = getViewsByType("music")
	config.plugins.dreamfin.defaultMusicView = ConfigSelection(default="0", choices=viewChoicesForMusic)

	printl("", "__init__::getViewTypesForSettings", "C")

#===============================================================================
#
#===============================================================================


def getViewsByType(myType):
	printl("", "__init__::getViewsByType", "S")
	views = getViews(myType)

	viewChoices = []
	i = 0
	for view in views:
		viewChoices.append((str(i), str(view[0])))
		i += 1

	printl("", "__init__::getViewsByType", "C")
	return viewChoices

#===============================================================================
#
#===============================================================================


def _(txt):
	#printl("", "__init__::_(txt)", "S")

	if len(txt) == 0:
		return ""
	text = gettext.dgettext("DreamFin", txt)
	if text == txt:
		text = gettext.gettext(txt)

	printl("text = " + str(text), "__init__::_(txt)", "D")

	#printl("", "__init__::_(txt)", "C")
	return text

#===============================================================================
# EXECUTE ON STARTUP
#===============================================================================


def prepareEnvironment():
	# the order here is important
	localeInit()
	getInstalledSkins()
	initBoxInformation()
	printGlobalSettings()
	initPlexServerConfig()
	registerSkinParamsInstance()
	loadSkinParams()
	checkSkinResolution()
	getViewTypesForSettings()
	checkPlexEnvironment()
	registerPlexFonts()
	loadPlexPlugins()

#===============================================================================
#
#===============================================================================


def startEnvironment():
	# reload BOTH the skin and the params on every plugin open (Phase 5): the
	# skin file picks the accent colour, loadSkinParams re-resolves the accent
	# highlight - so entering a server of a different type themes the whole UI on
	# the next open. loadSkinParams was boot-only, which left the highlight stuck.
	loadSkinParams()
	# we put load skin here to avoid bootloops if there is something wrong with the skin
	loadPlexSkin()
