import re
from io import StringIO
# from service.legacy.src import utilities
import os
import urllib


def sanitizeFileName(fileName):
    # TODO: 2020/06/30, Elvis - log that sanitization is happening if pattern is seen
    fileName = re.split(r'[/\\]', fileName)[-1]
    fileName = fileName.replace(' ', '_')
    # fileName = fileName.replace('-', '_')
    return fileName


def getPDBFile(path) -> str:
    """
        Obtain a PDB file.  First check the path given on the command
        line - if that file is not available, obtain the file from the
        PDB webserver at http://www.rcsb.org/pdb/ .
        Parameters
            path:  Name of PDB file to obtain (string)
        Returns
            file:  File object containing PDB file (file object)
    """

    # TODO: 2021/02/23, Elvis - Return the URL for the PDB file to download

    file = None
    if not os.path.isfile(path):
        URLpath = "https://files.rcsb.org/download/" + path + ".pdb"
        try:
            file = urllib.urlopen(URLpath)
            if file.getcode() != 200 or 'nosuchfile' in file.geturl():
                raise IOError
        except IOError:
            return None
    else:
        file = open(path, 'rU')
    return file


class WebOptionsError(Exception):
    def __init__(self, message, bad_key=None):
        super(WebOptionsError, self).__init__(message)
        self.bad_weboption = bad_key


class WebOptions(object):
    '''Helper class for gathering and querying options selected by the user'''
    def __init__(self, form):
        '''Gleans all information about the user selected options and uploaded files.
        Also validates the user input. Raises WebOptionsError if there is any problems.'''
        '''TODO: set second parameter of WebOptionError calls to specify bad key'''

        # options to pass to runPDB2PQR
        self.runoptions = {}
        # Additional options to pass to google analytics along with the run options.
        # These are included in has_key(), __contains__(), and __getitem__() calls.
        self.otheroptions = {}

        self.runoptions['debump'] = "DEBUMP" in form
        self.runoptions['opt'] = "OPT" in form

        if 'FF' in form:
            self.ff = form["FF"].lower()
        else:
            raise WebOptionsError('Force field type missing from form.')

        if "PDBID" in form and form["PDBID"] and form["PDBSOURCE"] == 'ID':
            # TODO: 2021/02/23, Elvis - Use PDBID to get URL/set flag for PDB file download
            pass
            # self.pdbfile = utilities.getPDBFile(form["PDBID"])
            # self.pdbfile = getPDBFile(form["PDBID"])
            self.user_did_upload = False
            # if self.pdbfile is None:
            #     raise WebOptionsError('The pdb ID provided is invalid.')
            # self.pdbfilestring = self.pdbfile.read()
            # self.pdbfile = StringIO(self.pdbfilestring)
            self.pdbfilename = form["PDBID"]

        elif form['PDBSOURCE'] == 'UPLOAD' and form['PDBFILE'] != '':
            # self.pdbfilestring = files["PDB"].stream.read()
            self.user_did_upload = True
            # self.pdbfile = StringIO(self.pdbfilestring)
            # self.pdbfilename = sanitizeFileName(files["PDB"].filename) # pass filename through client
            self.pdbfilename = sanitizeFileName(form['PDBFILE'])  # pass filename through client
            # print("filename: "+self.pdbfilename)
        else:
            raise WebOptionsError('You need to specify a pdb ID or upload a pdb file.')

        if "PKACALCMETHOD" in form:
            if form["PKACALCMETHOD"] != 'none':
                if 'PH' not in form:
                    raise WebOptionsError('Please provide a pH value.')

                phHelp = 'Please choose a pH between 0.0 and 14.0.'
                try:
                    ph = float(form["PH"])
                except ValueError:
                    raise WebOptionsError('The pH value provided must be a number!  ' + phHelp)
                if ph < 0.0 or ph > 14.0:
                    text = "The entered pH of %.2f is invalid!  " % ph
                    text += phHelp
                    raise WebOptionsError(text)
                self.runoptions['ph'] = ph
                # build propka and pdb2pka options
                if form['PKACALCMETHOD'] == 'propka':
                    self.runoptions['ph_calc_method'] = 'propka'
                    # self.runoptions['ph_calc_options'] = utilities.createPropkaOptions(ph, False)
                if form['PKACALCMETHOD'] == 'pdb2pka':
                    self.runoptions['ph_calc_method'] = 'pdb2pka'
                    self.runoptions['ph_calc_options'] = {'output_dir': 'pdb2pka_output',
                                                          'clean_output': True,
                                                          'pdie': 8,
                                                          'sdie': 80,
                                                          'pairene': 1.0}

        self.otheroptions['apbs'] = "INPUT" in form
        self.otheroptions['whitespace'] = "WHITESPACE" in form

        if self.ff == 'user':
            # if "USERFF") and form["USERFF"].filename:
            # self.userfffilename = sanitizeFileName(form["USERFF"].filename)
            if "USERFFFILE" in form and form["USERFFFILE"] != "":
                self.userfffilename = sanitizeFileName(form["USERFFFILE"])
                # self.userffstring = form["USERFF"]
                self.runoptions['userff'] = StringIO(form["USERFFFILE"])
            else:
                text = "A force field file must be provided if using a user created force field."
                raise WebOptionsError(text)

            # if form.has_key("USERNAMES") and form["USERNAMES"].filename:
            if "NAMESFILE" in form and form["NAMESFILE"] != "":
                self.usernamesfilename = sanitizeFileName(form["NAMESFILE"])
                # self.usernamesstring = form["USERNAMES"]
                self.runoptions['usernames'] = StringIO(form["NAMESFILE"])
            else:
                text = "A names file must be provided if using a user created force field."
                raise WebOptionsError(text)

        if "FFOUT" in form and form["FFOUT"] != "internal":
            self.runoptions['ffout'] = form["FFOUT"]

        self.runoptions['chain'] = "CHAIN" in form
        self.runoptions['typemap'] = "TYPEMAP" in form
        self.runoptions['neutraln'] = "NEUTRALN" in form
        self.runoptions['neutralc'] = "NEUTRALC" in form
        self.runoptions['drop_water'] = "DROPWATER" in form

        if (self.runoptions['neutraln'] or self.runoptions['neutraln']) and self.ff != 'parse':
            raise WebOptionsError('Neutral N-terminus and C-terminus require the PARSE forcefield.')

        # if form.has_key("LIGAND") and form['LIGAND'].filename:
            # self.ligandfilename=sanitizeFileName(form["LIGAND"].filename)
        if "LIGANDFILE" in form and form['LIGANDFILE'] != '':
            self.ligandfilename = sanitizeFileName(form["LIGANDFILE"])
            # ligandfilestring = form["LIGAND"]
            # for Windows and Mac style newline compatibility for pdb2pka
            # ligandfilestring = ligandfilestring.replace('\r\n', '\n')
            # self.ligandfilestring = ligandfilestring.replace('\r', '\n')

            # self.runoptions['ligand'] = StringIO(self.ligandfilestring)
            self.runoptions['ligand'] = StringIO(form["LIGANDFILE"])

        if self.pdbfilename[-4:] == ".pdb":
            self.pqrfilename = "%s.pqr" % self.pdbfilename[:-4]
        else:
            self.pqrfilename = "%s.pqr" % self.pdbfilename

        # Always turn on summary and verbose.
        self.runoptions['verbose'] = True
        self.runoptions['selectedExtensions'] = ['summary']

    def getLoggingList(self):
        '''Returns a list of options the user has turned on.
        Used for logging jobs later in usage.txt'''
        results = []

        for key in self:
            if self[key]:
                results.append(key)

        return results

    def getRunArguments(self):
        '''Returns argument suitable for runPDB2PQR'''
        return self.runoptions.copy()

    def getOptions(self):
        '''Returns all options for reporting to Google analytics'''
        options = self.runoptions.copy()
        options.update(self.otheroptions)

        options['ff'] = self.ff

        options['pdb'] = self.pdbfilename

        # propkaOptions is redundant.
        if 'ph_calc_options' in options:
            del options['ph_calc_options']

        if 'ligand' in options:
            options['ligand'] = self.ligandfilename

        if 'userff' in options:
            options['userff'] = self.userfffilename

        if 'usernames' in options:
            options['usernames'] = self.usernamesfilename

        return options

    def getCommandLine(self):
        commandLine = []

        if not self.runoptions['debump']:
            commandLine.append('--nodebump')

        if not self.runoptions['opt']:
            commandLine.append('--noopt')

        if 'ph' in self.runoptions:
            commandLine.append('--with-ph=%s' % self.runoptions['ph'])

        if 'ph_calc_method' in self.runoptions:
            commandLine.append('--ph-calc-method=%s' % self.runoptions['ph_calc_method'])

        if self.runoptions['drop_water']:
            commandLine.append('--drop-water')

        if self.otheroptions['apbs']:
            commandLine.append('--apbs-input')

        if self.otheroptions['whitespace']:
            commandLine.append('--whitespace')

        if 'userff' in self.runoptions and self.ff == 'user':
            commandLine.append('--userff=%s' % self.userfffilename)
            commandLine.append('--usernames=%s' % self.usernamesfilename)
        else:
            commandLine.append('--ff=%s' % self.ff)

        if 'ffout' in self.runoptions:
            commandLine.append('--ffout=%s' % self.runoptions['ffout'])

        for o in ('chain', 'typemap', 'neutraln', 'neutralc', 'verbose'):
            if self.runoptions[o]:
                commandLine.append('--' + o)

        if 'ligand' in self.runoptions:
            commandLine.append('--ligand=%s' % self.ligandfilename)

        for ext in self.runoptions.get('selectedExtensions', []):
            commandLine.append('--%s' % ext)

        commandLine.append(self.pdbfilename)

        commandLine.append(self.pqrfilename)

        return ' '.join(commandLine)

    def __contains__(self, item):
        '''Helper for checking for the presence of an option'''
        return item in self.runoptions or item in self.otheroptions

    def has_key(self, item):
        '''Helper for checking for the presence of an option'''
        return item in self.runoptions or item in self.otheroptions

    def __iter__(self):
        for key in self.runoptions:
            yield key

        for key in self.otheroptions:
            yield key

    def __getitem__(self, key):
        return self.runoptions[key] if key in self.runoptions else self.otheroptions[key]
