#!/usr/bin/env python
# syntax <build_board.py> <output_dir> <platform> <board_name> [<group name>]
import os,sys
import sys
import helper_func
from helper_func import *
try:
    from lxml import etree
except ImportError:
    try:
        # Python 2.5
        import xml.etree.cElementTree as etree
    except ImportError:
        # Python 2.5
        import xml.etree.ElementTree as etree

########################################
# Catalog Parsing Helper Functions
########################################

###############
# Find File
###############
def _find_file(baseDir,filePath, tag=""):

    if not os.path.isabs(filePath):
        # First search relative to the board xml file
        if tag == "dts":
            baseDir = baseDir + "/dts"
        elif tag == "fsbl" or tag == "bit":
            baseDir = baseDir + "/boot"                
        else:
            baseDir = baseDir
        filePath = os.path.realpath(baseDir + "/" + filePath)
    if not (os.path.isfile(filePath) or os.path.isdir(filePath)):
        filePath = None
    return filePath

###############
# Load App
###############
def _load_app(xmlApp, loadDefaults=True):

    if loadDefaults and (not _defaults['app'] is None):
        appInfo = dict(_defaults['app'])
    else:
        appInfo = dict()
    appInfo['name'] = xmlApp.get('name')
    appInfo['buildBoot'] = False
    for element in xmlApp:
        tag = element.tag
        fileSrc = element.get('file')
        if fileSrc is None:
            fileSrc = element.get('dir')
        
        # First search relative to the board xml file, in the specified directories
        filePath = _find_file(_CATALOG_DIR,fileSrc, tag=tag)
        if filePath is None:
            # Next search relative to the board xml file
            filePath = _find_file(_CATALOG_DIR,fileSrc)
            if filePath is None:
                # Last search in the board directory
                filePath = _find_file(_defaults['boardInfo']['dir'],fileSrc, tag=tag)
        
        if filePath is None:                
            raise IOError("[App: %s]Cannot find %s file: %s" %(appInfo['name'], tag, fileSrc))

        appInfo[tag] = filePath
        if tag == "bit" or tag == "fsbl" or tag == "handoff":
            appInfo['buildBoot'] = True
    return appInfo


###############
# Find SD dir
###############
def _find_sd_dir(xmlNode, loadDefaults=True):
    sdNode = xmlNode.find('sdcard')
    platformDir = "%s/%s" % (MW_DIR, _PLATFORM_NAME)
    if sdNode is None:
        if loadDefaults:
            # no value specified, use already resolved default
            startDir = ""
            sdSrc = _defaults['sdcardDir']
        else:
            # no value specified, only search the platform directory
            startDir = platformDir
            sdSrc = "sdcard"
    else:
        # value specified, search relative to the catalog file
        startDir = _CATALOG_DIR
        sdSrc = sdNode.get('dir')
    
    # Try the first search path
    filePath = _find_file(startDir, sdSrc)
    if filePath is None:
        # Next search in the platform directory
        filePath = _find_file(platformDir, sdSrc)
        if filePath is None:
            raise IOError("[Image: %s]Cannot find specified sdcard dir: %s" % (xmlNode.get('name'), sdSrc))
    return filePath

###############
# Add Include Dir
###############
def _add_include_dir(dirStr, dirList=None):
    if dirList is None:
        dirList = list()
    filePath = _find_file(_CATALOG_DIR, dirStr)      
    if filePath is None:
        raise IOError("Cannot find specified include directory: %s" % (dirStr))
    dirList.append(filePath)
    return dirList

###############
# Load Image
###############
def _load_image(imageNode):
    imageInfo = dict()
    appList = []
    for app in imageNode.findall('app'):
        appInfo = _load_app(app)
        appList.append(appInfo)

    # Determine the sd card source directory
    imageInfo['sdcardDir'] = _find_sd_dir(imageNode)

    # Build the DTS include dirs
    imageInfo['dtsIncDirs'] = _defaults['dtsIncDirs']
    for dtsi in imageNode.findall('dtsi'):
        _add_include_dir(dtsi.get('dir'),imageInfo['dtsIncDirs'])

    imageInfo['imageName'] = imageNode.get('name') 
    imageInfo['appList'] = appList
    imageInfo['defaultApp'] = appList[0]
    return imageInfo

###############
# Load Board Info
###############
def _load_board_info(boardNode):
    boardInfo = dict()
    # load the node
    if boardNode is None:
        boardDir = None
    else:
        boardDir = boardNode.get('dir')

    # Parse the node
    if boardDir is None:
        boardInfo['dir'] = "%s/%s/boards/%s" % (MW_DIR, _PLATFORM_NAME, _BOARD_NAME)
    else:
        boardInfo['dir'] = _find_file(_CATALOG_DIR,boardDir)
        if boardInfo['dir'] is None:
            raise IOError("Cannot find specified board directory: %s" % (boardDir))

    return boardInfo

###############
# Load Local Config Info
###############
def _find_local_file(fileNode):

    # load the node
    if fileNode is None:
        cfgFile = None
    else:
        cfgFile = _find_file(_CATALOG_DIR,fileNode.get('file'))
        if cfgFile is None:
            raise IOError("Cannot find specified %s file: %s" % (fileNode.tag, fileNode.get('file')))
    
    return cfgFile

###############
# Load Defaults
###############
def _load_defaults(defNode):
    global _defaults
    # Load the board node, if present
    boardNode = defNode.find('board_dir')
    _defaults['boardInfo'] = _load_board_info(boardNode)
    # Load the default files for apps
    appNode = defNode.find('app')
    if not appNode is None:
        _defaults['app'] = _load_app(appNode, loadDefaults=False)
    else:
        _defaults['app'] = None

    # Load the default SD card directory
    _defaults['sdcardDir'] = _find_sd_dir(defNode, loadDefaults=False)
    _defaults['dtsIncDirs'] = list()
    # Load the global include directories
    for dtsi in defNode.findall('dtsi'):
        _add_include_dir(dtsi.get('dir'),_defaults['dtsIncDirs'])
    # Load the extra br2 config files
    _defaults['br2_config'] = _find_local_file(defNode.find('br2_config'))
    # Load the kernel config file
    _defaults['kernel_config'] = _find_local_file(defNode.find('kernel_config'))

########################################
# Public Functions
########################################
###############
# Read the catalog file
###############
def read_catalog(catalogFile, imageNames=["all"]):
    global _CATALOG_DIR
    global _PLATFORM_NAME
    global _BOARD_NAME

    # Determine the board dir
    _CATALOG_DIR = os.path.dirname(os.path.realpath(catalogFile))
    # read in the tree
    tree = etree.parse(catalogFile)
    root = tree.getroot()

    # Now capture some info
    _PLATFORM_NAME = root.get('platform')
    _BOARD_NAME = root.get('name')

    # determine the group configuration
    if imageNames == ["all"]:
        allImages = True

    # First capture the default settings
    defNode = root.find('default')
    _load_defaults(defNode)

    # Now parse the images
    imageList = list()
    for image in root.findall('image'):
        imageName = image.get('name')
        if allImages or (imageName in imageNames):
            imageInfo = _load_image(image)            
        else:
            continue
        if len(imageInfo['appList']) == 0:
            raise ValueError("No applications found for image: %s" % (imageName))     

        imageList.append(imageInfo)

    # Turn on the boot build for the first (main) app
    for image in imageList:    
        image['appList'][0]['buildBoot'] = True       
    
    # Create the catalog
    catalog = dict()
    catalog['boardName'] = _BOARD_NAME
    catalog['platformName'] = _PLATFORM_NAME
    catalog['platformDir'] = os.path.dirname(COMMON_DIR) + "/" + catalog['platformName']
    catalog['catalogDir'] = _CATALOG_DIR
    catalog['defaultInfo'] = _defaults
    catalog['imageList'] = imageList

    return catalog

########################################
# Module Globals
########################################
_defaults = dict()
_CATALOG_DIR = ""
_PLATFORM_NAME = ""
_BOARD_NAME = ""
