#!/usr/bin/env python

import ROOT
import re
import pprint
import sys
import inspect
import optparse

defsDict = {
    'int'    : '%-40s : form=%%%%8d     type=int',
    'float'  : '%-40s : form=%%%%7.2f   prec=0.001',
    'str'    : '%-40s : form=%%%%20s    type=string',
    'long'   : '%-40s : form=%%%%10d    type=long',    
    }

root2GOtypeDict = {
    'int'                      : 'int',
    'float'                    : 'float',
    'double'                   : 'float',
    'long'                     : 'long',
    'long int'                 : 'long',
    'unsigned int'             : 'int',
    'bool'                     : 'int',
    'string'                   : 'str',
    'std::basic_string<char>'  : 'str',
    }

colonRE     = re.compile (r':')
dotRE       = re.compile (r'\.')
nonAlphaRE  = re.compile (r'\W')
alphaRE     = re.compile (r'(\w+)')
vetoedTypes = set()


def getObjectList (objectName, base):
    """Get a list of interesting things from this object"""
    # The autoloader needs an object before it loads its dictionary.
    # So let's give it one.
    rootObjConstructor = getattr (ROOT, objectName)
    obj = rootObjConstructor()
    alreadySeenFunction = set()
    global vetoedTypes
    retval = []
    # Put the current class on the queue and start the while loop
    reflexList = [ ROOT.Reflex.Type.ByName (objectName) ]
    while reflexList:
        reflex = reflexList.pop (0) # get first element
        print "Looking at %s" % reflex.Name (0xffffffff)
        for baseIndex in range( reflex.BaseSize() ) :
            reflexList.append( reflex.BaseAt(baseIndex).ToType() )
        for index in range( reflex.FunctionMemberSize() ):
            funcMember = reflex.FunctionMemberAt (index)
            # if we've already seen this, don't bother again
            name = funcMember.Name()
            if name  in alreadySeenFunction:
                continue
            # make sure this is an allowed return type
            returnType = funcMember.TypeOf().ReturnType().Name (0xffffffff)
            goType     = root2GOtypeDict.get (returnType, None)
            if not goType:
                vetoedTypes.add (returnType)
                continue
            # only bother printout out lines where it is a const function
            # and has no input parameters.            
            if funcMember.IsConst() and not funcMember.FunctionParameterSize():
                retval.append( ("%s.%s()" % (base, name), goType))
                #print "  %3d) %-30s %-20s" % (index, name, returnType)
                alreadySeenFunction.add( name )
    retval.sort()
    return retval


def genObjNameDef (line):
    """Returns GenObject name and ntuple definition function"""
    words = dotRE.split (line)[1:]
    func = ".".join (words)
    name =  "_".join (words)
    name = nonAlphaRE.sub ('', name)
    return name, func
    
    
def genObjectDef (mylist, tuple, alias, full):
    """ """
    print "tuple %s alias %s full %s" % (tuple, alias, full)
    # first get the name of the object
    firstName = mylist[0][0]
    match = alphaRE.match (firstName)
    if not match:
        raise RuntimeError, "firstName doesn't parse correctly. (%s)" \
              % firstName
    genName = match.group (1)
    genDef =  " ## GenObject %s Definition ##\n[%s]\n" % \
             (genName, genName)
    genDef += "-equiv: eta,0.1 phi,0.1\n";
    tupleDef = '[%s:%s:%s alias=%s]\n' % \
               (genName, tuple, alias, full)
    
    for variable in mylist:
        name, func = genObjNameDef (variable[0])
        ## if name in alreadySeenSet:
        ##     raise RuntineError, "Duplicate '%s'" % name
        ## alreadySeenSet.add (name)
        typeInfo   = variable[1]
        form = defsDict[ typeInfo ]
        genDef   += form % name + '\n'
        tupleDef += "%-40s : %s\n" % (name, func)
    return genDef, tupleDef


if __name__ == "__main__":
    # Setup options parser
    parser = optparse.OptionParser \
             ("usage: %prog [options] output.txt  objectName\n" \
              "Creates control file for GenObject.")
    parser.add_option ('--output', dest='output', type='string',
                       default = '',
                       help="Output (Default 'objectName.txt')")
    parser.add_option ('--alias', dest='alias', type='string',
                       default = 'dummyAlias',
                       help="Tell GO to set an alias")
    parser.add_option ('--goName', dest='goName', type='string',
                       default='',
                       help='GenObject name')
    parser.add_option ('--tupleName', dest='tupleName', type='string',
                       default = 'reco',
                       help="Tuple name (default '%default')")
    options, args = parser.parse_args()
    if len (args) < 1:
        print "Need to provide output file, and Root name"\
              ". Aborting."
        sys.exit(1)
    #
    objectName = args[0]    
    goName     = options.goName or colonRE.sub ('', objectName)
    outputFile = options.output or goName + '.txt'
    ROOT.gROOT.SetBatch()
    # load the right libraries, etc.
    ROOT.gSystem.Load("libFWCoreFWLite")
    ROOT.gSystem.Load("libDataFormatsFWLite")   
    ROOT.gSystem.Load("libReflexDict")
    ROOT.AutoLibraryLoader.enable()
    mylist = getObjectList (objectName, goName)
    targetFile = open (outputFile, 'w')
    genDef, tupleDef = genObjectDef (mylist,
                                     options.tupleName,
                                     goName,
                                     options.alias)
    targetFile.write ("# -*- sh -*- For Font lock mode\n# GenObject 'event' definition\n[runevent singleton]\nrun:   type=int\nevent: type=int\n\n")
    targetFile.write (genDef)
    targetFile.write ('\n\n# %s Definition\n# Nickname and Tree\n[%s:Events]\n'\
                      % (options.tupleName, options.tupleName));
    targetFile.write ('[runevent:%s:EventAuxiliary]\nrun:   id_.run()\nevent: id_.event()\n\n' % options.tupleName)
    targetFile.write (tupleDef)
    print "Vetoed types:"
    pprint.pprint ( sorted( list(vetoedTypes) ) )
