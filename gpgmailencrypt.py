#!/usr/bin/python
# -*- coding: utf-8 -*- 
#based on gpg-mailgate
#License GPL v3
#Author Horst Knorr <gpgmailencryt@gmx.de>
from ConfigParser import ConfigParser
from email import Encoders
import email,email.message,email.mime,email.mime.base,email.mime.multipart,email.mime.application,email.mime.text,smtplib,mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import HTMLParser 
import re,sys,tempfile,os,subprocess,atexit,time,getopt,random,syslog,inspect,gzip
from email.generator import Generator
from cStringIO import StringIO
from os.path import expanduser

VERSION="1.1.0zeta"
DATE="30.06.2015"
#################################
#Definition of general functions#
#################################
#####
#init
#####
def init():
	global logfile,addressmap,encryptionmap,smimeuser,tempfiles
	global mailcount,o_mail,o_stdout,o_file,l_none,l_syslog,l_file,l_stderr
	global m_daemon,m_script
	global encryptgpgcomment,encryptheader
	global DEBUG,LOGGING,LOGFILE,ADDHEADER,HOST,PORT,DOMAINS,CONFIGFILE
	global INFILE,OUTFILE,PREFER_GPG,PGPMIME,GPGKEYHOME,ALLOWGPGCOMMENT,GPGCMD
	global SMIMEKEYHOME,SMIMECMD,SMIMECIPHER,SMIMEKEYEXTRACTDIR,SMIMEAUTOMATICEXTRACTKEYS
	global SPAMSUBJECT,OUTPUT, DEBUGSEARCHTEXT,DEBUGEXCLUDETEXT,LOCALE,LOCALEDB
	global RUNMODE,SERVERHOST,SERVERPORT

	#Internal variables
	atexit.register(do_finally_at_exit)
	logfile=None
	addressmap = dict()
	encryptionmap = dict()
	smimeuser = dict()
	tempfiles = list()
	mailcount=0
	o_mail=1
	o_stdout=2
	o_file=3
	l_none=1
	l_syslog=2
	l_file=3
	l_stderr=4
	m_daemon=1
	m_script=2
	encryptgpgcomment="Encrypted by gpgmailencrypt version %s"%VERSION
	encryptheader="X-GPGMailencrypt"

	#GLOBAL CONFIG VARIABLES
	DEBUG=False
	LOGGING=l_none
	LOGFILE=""
	ADDHEADER=False
	HOST='localhost'
	PORT=25
	SERVERHOST="127.0.0.1"
	SERVERPORT=1025
	DOMAINS=""
	CONFIGFILE='/etc/gpgmailencrypt.conf'
	INFILE=""
	OUTFILE=""
	PREFER_GPG=True
	PGPMIME=False
	GPGKEYHOME="~/.gnupg"
	ALLOWGPGCOMMENT=False
	GPGCMD='/usr/bin/gpg2'
	SMIMEKEYHOME="~/.smime"
	SMIMEKEYEXTRACTDIR="%s/extract"%SMIMEKEYHOME
	SMIMECMD="/usr/bin/openssl"
	SMIMECIPHER="DES3"
	SMIMEAUTOMATICEXTRACTKEYS=False
	SPAMSUBJECT="***SPAM"
	OUTPUT=o_mail 
	DEBUGSEARCHTEXT=[]
	DEBUGEXCLUDETEXT=[]
	LOCALE="EN"
	LOCALEDB={
	"DE":("Termin","Datei"),
	"EN":("appointment","file"),
	"ES":("cita","fichero"),
	"FR":("rendez-vous","fichier"),
	}
	RUNMODE=m_script
	if DEBUG:
		for a in addressmap:
			debug("addressmap: '%s'='%s'"%(a,addressmap[a]))
############
#set_logmode
############
def set_logmode():
	global logfile,LOGGING,LOGFILE
	try:
		if LOGGING==l_file and len(LOGFILE)>0:
			logfile = open(LOGFILE, 'a')
	except:
		logfile=None
		LOGGING=l_stderr
		log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
####
#log
####
def log(msg,infotype="m",ln=-1):
	global logfile
	if LOGGING!=l_none:
		if ln==-1:
			ln=inspect.currentframe().f_back.f_lineno
		_lftmsg=20
		prefix="Info"
		if infotype=='w':
			prefix="Warning"
		elif infotype=='e':
			prefix="Error"
		elif infotype=='d':
			prefix="Debug"
		t=time.localtime(time.time())
		_lntxt="Line %i: "%ln
		tm=("%02d.%02d.%04d %02d:%02d:%02d:" % (t[2],t[1],t[0],t[3],t[4],t[5])).ljust(_lftmsg)
		if (ln>0):
			msg=_lntxt+str(msg)
		if LOGGING==l_syslog:
			#write to syslog
			level=syslog.LOG_INFO
			if infotype=='w':
				level=syslog.LOG_WARNING
			elif infotype=='e':
				level=syslog.LOG_ERR
				msg="ERROR "+msg
			elif infotype=='d':
				level=syslog.LOG_DEBUG
				msg="DEBUG "+msg
			syslog.syslog(level,msg)
		elif  LOGGING==l_file and logfile!=None:
			#write to logfile
			logfile.write("%s %s: %s\n"%(tm,prefix,msg ))
		else:
			# print to stderr if nothing else works
			sys.stdout.write("%s %s: %s\n"%(tm,prefix,msg ))
######
#debug
######
def debug(msg):
	if DEBUG:
		ln=inspect.currentframe().f_back.f_lineno
		log(msg,"d",ln)
################
#debug_keepmail
################
def debug_keepmail(mailtext):
	for txt in DEBUGSEARCHTEXT:
		if txt in mailtext:
			for exclude in DEBUGEXCLUDETEXT:
				if exclude in mailtext:
					return False
			return True
	return False
###########
#show_usage
###########
def show_usage():
	print ("gpgmailencrypt")
	print ("===============")
	print ("based on gpg-mailgate")
	print ("License: GPL 3")
	print ("Author:  Horst Knorr")
	print ("Version: %s from %s"%(VERSION,DATE))
	print ("\nUsage:\n")
	print ("gpgmailencrypt [options] receiver@email.address < Inputfile_from_stdin")
	print ("\nOptions:\n")
	print ("-a --addheader:  adds %s header to the mail"%encryptheader)
	print ("-c f --config f: use configfile 'f'. Default is /etc/gpgmailencrypt.conf")
	print ("-d --daemon :    start gpgmailencrypt as smtpserver")
	print ("-e gpg :         preferred encryption method, either 'gpg' or 'smime'")
	print ("-f mail :        reads email file 'mail', otherwise from stdin")
	print ("-h --help :      print this help")
	print ("-k f --keyhome f:sets gpg key directory to 'f'")
	print ("-l t --log t:    print information into logfile, with valid types 't' 'none','stderr','syslog','file'")
	print ("-n domainnames:  sets the used domain names (comma separated lists, no space), which should be encrypted, empty is all")
	print ("-m mailfile :    write email file to 'mailfile', otherwise email will be sent via smtp")
	print ("-o p --output p: valid values for p are 'mail' or 'stdout', alternatively you can set an outputfile with -m")
	print ("-p --pgpmime:    create email in PGP/MIME style")
	print ("-x --example:    print example config file")
	print ("-v --verbose:    print debugging information into logfile")
	print ("")
####################
#print_exampleconfig
####################
def print_exampleconfig():
	print ("[default]")
	print ("preferred_encryption = gpg    			; valid values are 'gpg' or 'smime'")
	print ("add_header = no         			; adds a %s header to the mail"%encryptheader)
	print ("domains =    		     			; comma separated list of domain names, \
that should be encrypted, empty is all")
	print ("spamsubject =***SPAM				; Spam recognition string, spam will not be encrypted")
	print ("output=mail 					; valid values are 'mail'or 'stdout'")
	print ("locale=en 					; DE|EN|ES|FR'")
	print ("")
	print ("[gpg]")
	print ("send_pgpmime = no       			; sends email in PGP/MIME style, otherwise encrypts each attachment")
	print ("keyhome = /var/lib/gpgmailencrypt/.gnupg   	; home directory of public  gpgkeyring")
	print ("gpgcommand = /usr/bin/gpg2")
	print ("allowgpgcomment = yes				; allow a comment string in the GPG file")
	print ("")
	print ("[logging]")
	print ("log=none 					; valid values are 'none', 'syslog', 'file' or 'stderr'")
	print ("file = /tmp/gpgmailencrypt.log")
	print ("debug = no")
	print ("")
	print ("host = 127.0.0.1				;smtp host")
	print ("port = 25	    				;smtp port")
	print ("")
	print ("[usermap]")
	print (";user_nokey@domain.com = user_key@otherdomain.com")
	print ("")
	print ("[smime]")
	print ("keyhome = ~/.smime				;home directory of S/MIME public key files")
	print ("opensslcommand = /usr/bin/openssl")
	print ("defaultcipher = DES3				;DES3|AES128|AES192|AES256")
	print ("extractkey= no					;automatically scan emails and extract smime public keys to 'keyextractdir'")
	print ("keyextractdir=~/.smime/extract")
	print ("")
	print ("[smimeuser]")
	print ("smime.user@domain.com = user.pem[,cipher]	;public S/MIME key file [,used cipher, see defaultcipher]\n")
	print ("")
	print ("[encryptionmap]    ")
	print ("user@domain.com = PGPMIME		;PGPMIME|PGPINLINE|SMIME|NONE\n")
	print ("")
	print ("[daemon]")
	print ("host = 127.0.0.1				;smtp host")
	print ("port = 10025    				;smtp port")
###############
#prepare_syslog
###############
def prepare_syslog():
		global LOGGING
		LOGGING=l_syslog
		syslog.openlog("gpgmailencrypt",syslog.LOG_PID,syslog.LOG_MAIL)
################
#read_configfile
################	
def read_configfile():
	global addressmap,encryptionmap,GPGCMD,DEBUG,DOMAINS,LOGGING,LOGFILE,GPGKEYHOME,PREFER_GPG
	global ADDHEADER,PGPMIME,HOST,PORT,ALLOWGPGCOMMENT,CONFIGFILE,SPAMSUBJECT,OUTPUT
	global smimeuser,SMIMEKEYHOME,SMIMECMD,SMIMECIPHER,SMIMEKEYEXTRACTDIR,SMIMEAUTOMATICEXTRACTKEYS
	global DEBUGEXCLUDETEXT,DEBUGSEARCHTEXT
	global LOCALE,SERVERHOST,SERVERPORT
	_cfg = ConfigParser()
	try:
		_cfg.read(CONFIGFILE)
	except:
		log("Could not read config file '%s'"%CONFIGFILE,"e")
		return

	if _cfg.has_section('default'):
		if _cfg.has_option('default','add_header'):
			ADDHEADER=_cfg.getboolean('default','add_header')
		if _cfg.has_option('default','output'):
			o=_cfg.get('default','output').lower().strip()
			if o=="mail":
				OUTPUT=o_mail
			elif o=="stdout":
				OUTPUT=o_stdout
			elif o=="file":
				OUTPUT=o_file
			else:
				OUTPUT=o_stdout
		if _cfg.has_option('default','locale'):
			LOCALE=_cfg.get('default','locale').upper().strip()
		if _cfg.has_option('default','domains'):
			DOMAINS=_cfg.get('default','domains')
		if _cfg.has_option('default','spamsubject'):
			SPAMSUBJECT=_cfg.get('default','spamsubject')
		if _cfg.has_option('default','preferred_encryption'):
			p=_cfg.get('default','preferred_encryption').lower()
			if p=="smime":
				PREFER_GPG=False
			else:
				PREFER_GPG=True

	if _cfg.has_section('logging'):
		if _cfg.has_option('logging','log'):
			l=_cfg.get('logging','log').lower()
			if l=="syslog":
				LOGGING=l_syslog
				prepare_syslog()
			elif l=='file':
				LOGGING=l_file
			elif l=='stderr':
				LOGGING=l_stderr
			else:
				LOGGING=l_none
		if _cfg.has_option('logging','file'):
			LOGFILE=_cfg.get('logging','file')
		if _cfg.has_option('logging','debug'):
			DEBUG=_cfg.getboolean('logging','debug')
		if _cfg.has_option('logging','debugsearchtext'):
			s=_cfg.get('logging','debugsearchtext')
			if len(s)>0:
				DEBUGSEARCHTEXT=s.split(",")
		if _cfg.has_option('logging','debugexcludetext'):
			e=_cfg.get('logging','debugexcludetext')
			if len(e)>0:
				DEBUGEXCLUDETEXT=e.split(",")
	if _cfg.has_section('gpg'):
		if _cfg.has_option('gpg','send_pgpmime'):
			PGPMIME=_cfg.getboolean('gpg','send_pgpmime')
		if _cfg.has_option('gpg','keyhome'):
			k=_cfg.get('gpg','keyhome')
			if k!=None:
				GPGKEYHOME=k.strip()
		if _cfg.has_option('gpg','gpgcommand'):
			GPGCMD=_cfg.get('gpg','gpgcommand')
		if _cfg.has_option('gpg','allowgpgcomment'):
			ALLOWGPGCOMMENT=_cfg.getboolean('gpg','allowgpgcomment')

	if _cfg.has_section('mailserver'):
		if _cfg.has_option('mailserver','host'):
			HOST=_cfg.get('mailserver','host')
		if _cfg.has_option('mailserver','port'):
			PORT=_cfg.getint('mailserver','port')

	if _cfg.has_section('usermap'):
		for (name, value) in _cfg.items('usermap'):
				addressmap[name] = value
	if _cfg.has_section('encryptionmap'):
		for (name, value) in _cfg.items('encryptionmap'):
				encryptionmap[name] = value
	if _cfg.has_section('daemon'):
		if _cfg.has_option('daemon','host'):
			SERVERHOST=_cfg.get('daemon','host')
		if _cfg.has_option('daemon','port'):
			SERVERPORT=_cfg.getint('daemon','port')

	# smime extra
	if _cfg.has_section('smime'):
		if _cfg.has_option('smime','opensslcommand'):
			SMIMECMD=_cfg.get('smime','opensslcommand')
		if _cfg.has_option('smime','defaultcipher'):
			SMIMECIPHER=_cfg.get('smime','defaultcipher').upper().strip()
		if _cfg.has_option('smime','keyhome'):
			k=_cfg.get('smime','keyhome')
			if k!=None:
				SMIMEKEYHOME=k.strip()
		if _cfg.has_option('smime','extractkey'):
			SMIMEAUTOMATICEXTRACTKEYS=_cfg.getboolean('smime','extractkey')
	
		if _cfg.has_option('smime','keyextractdir'):
			k=_cfg.get('smime','keyextractdir')
			if k!=None:
				SMIMEKEYEXTRACTDIR=k.strip()
	s=SMIME(SMIMEKEYHOME)
	smimeuser.update(s.create_keylist(SMIMEKEYHOME))
	if _cfg.has_section('smimeuser'):
		for (name, value) in _cfg.items('smimeuser'):
			user=value.split(",")
			cipher=SMIMECIPHER
			if len(user)==2:
				cipher=user[1].upper().strip()
			path=os.path.expanduser(os.path.join(SMIMEKEYHOME,user[0]))
			if os.path.isfile(path):
				smimeuser[name] = [path,cipher]
	set_logmode()
	if DEBUG:
		for u in smimeuser:
			debug("SMimeuser: '%s %s'"%(u,smimeuser[u]))

#################
#parse_commandline
##################
def parse_commandline():
	receiver=[]
	global DEBUG,CONFIGFILE,LOGGING,LOGFILE,GPGKEYHOME,ADDHEADER,PGPMIME,HOST,PORT,INFILE,OUTFILE,OUTPUT
	global PREFER_GPG,RUNMODE
	try:
		cl=sys.argv[1:]
		_opts,_remainder=getopt.gnu_getopt(cl,'ac:de:f:hk:l:m:n:o:pvxy',
  		['addheader','config=','daemon','example','help','keyhome=','log=','output=','pgpmime','verbose'])
	except getopt.GetoptError,e:
		LOGGING=l_stderr
		log("unknown commandline parameter '%s'"%e,"e")
		exit(2)

	for _opt, _arg in _opts:
		if _opt  =='-l' or  _opt == '--log':
	   		LOGGING=l_stderr
	   		if type(_arg)==str:
				if _arg=="syslog":
					LOGGING=l_syslog
					prepare_syslog
				else:
					LOGGING=l_stderr

	for _opt, _arg in _opts:
		if (_opt  =='-c' or  _opt == '--config') and _arg!=None:
	   		_arg=_arg.strip()
	   		if len(_arg)>0:
	   			CONFIGFILE=_arg
	   			log("read new config file '%s'"%CONFIGFILE)
	   			read_configfile()
	   			break

	for _opt, _arg in _opts:
		if _opt  =='-a' or  _opt == '--addheader':
	   		ADDHEADER=True
		if _opt  =='-v' or  _opt == '--verbose':
	   		DEBUG=True
		if _opt  =='-e':
			if _arg=="smime":
				PREFER_GPG=False
				debug("Set PREFER_GPG to False: => S/MIME preferred")
			else:
				PREFER_GPG=True
				debug("Set PREFER_GPG to True: => GPG preferred")
		if _opt  =='-f':
	   		INFILE=expanduser(_arg)
	   		debug("Set INFILE to '%s'"%INFILE)
		if _opt  =='-h' or  _opt == '--help':
	   		show_usage()
	   		exit(0)
		if _opt  =='-k' or  _opt == '--keyhome':
	   		GPGKEYHOME=_arg
	   		debug("Set gpgkeyhome to '%s'"%GPGKEYHOME)
		if _opt  =='-l' or  _opt == '--log':
	   		LOGGING=l_stderr
	   		if type(_arg)==str:
				if _arg=="syslog":
					LOGGING=l_syslog
				elif _arg=='file':
					LOGGING=l_file
				else:
					LOGGING=l_stderr

		if _opt  =='-o' or  _opt == '--output':
	   		if type(_arg)==str:
				if _arg=="mail":
					OUTPUT=o_mail
				elif _arg=="stdout":
					OUTPUT=o_stdout
				elif _arg=="file":
					OUTPUT=o_file
				else:
					OUTPUT=o_stdout
		if _opt  =='-p' or  _opt == '--pgpmime':
	   		PGPMIME=True
		if _opt  =='-m':
	   		OUTFILE=expanduser(_arg)
	   		OUTPUT=o_file
	   		debug("Set OUTFILE to '%s'"%OUTFILE)
		if (_opt  =='-s' or  _opt == '--stdout') and len(OUTFILE)==0:
		   	OUTPUT=o_stdout
		if (_opt  =='-d' or  _opt == '--daemon'):
		   	RUNMODE=m_daemon
		if _opt  =='-x' or  _opt == '--example':
	   		print_exampleconfig()
	   		exit(0)
	if not RUNMODE==m_daemon:
		if len(_remainder)>0 :
			receiver=_remainder[0:]
			debug("set addresses from commandline to '%s'"%receiver)
		else:
			LOGGING=l_stderr
			log("gpgmailencrypt needs at least one recipient at the commandline, %i given"%len(_remainder),"e")
			exit(1)
	return receiver
################
#set_output2mail
################
def set_output2mail():
	global OUTFILE,OUTPUT
	OUTPUT=o_mail
################
#set_output2file
################
def set_output2mail(mailfile=None):
	global OUTFILE,OUTPUT
	OUTFILE=expanduser(_arg)
	OUTPUT=o_file
##################
#set_output2stdout
##################
def set_output2stdout():
	global OUTFILE,OUTPUT
	OUTPUT=o_stdout
##########
#set_debug
##########
def set_debug(dbg):
	global DEBUG
	if dbg:
		DEBUG=True
	else:
		DEBUG=False
##########
#set_pgpmime
##########
def set_pgpmime(mime):
	global PGPMIME
	if mime:
		PGPMIME=True
	else:
		PGPMIME=False

##############
#make_boundary
##############
def make_boundary(text=None):
    _width = len(repr(sys.maxint-1))
    _fmt = '%%0%dd' % _width    
    token = random.randrange(sys.maxint)
    boundary = ('=' * 15) + (_fmt % token) + '=='
    if text is None:
        return boundary
    b = boundary
    counter = 0
    while True:
        cre = re.compile('^--' + re.escape(b) + '(--)?$', re.MULTILINE)
        if not cre.search(text):
            break
        b = boundary + '.' + str(counter)
        counter += 1
    return b
#############
#find_charset
#############
def find_charset(msg):
	if type(msg) != str:
		return None
	find=re.search("^Content-Type:.*charset=[-_\.\'\"0-9A-Za-z]+",msg,re.I|re.MULTILINE)
	if find==None:
		return None
	charset=msg[find.start():find.end()]
	res=charset.split("=")
	if len(res)<2:
		return None
	charset=str(res[1]).replace('"','').replace("'","")
	return charset
#############
#new_tempfile
#############
def new_tempfile():
	global tempfiles
	f=tempfile.NamedTemporaryFile(mode='wb',delete=False,prefix='mail-')
	tempfiles.append(f.name)
	debug("new_tempfile %s"%f.name)

	return f
#############
#del_tempfile
#############
def del_tempfile(f):
	global tempfiles
	n=""
	if type(f)!=str:
		return
	debug("del_tempfile:%s"%f)
	try:
		tempfiles.remove(f)
	except:
		pass
	try:
		os.remove(f)
	except:
		pass
#########
#send_msg
#########
def send_rawmsg(mailtext,msg,from_addr, to_addr):
	debug("send_rawmsg")
	try:
		message = email.message_from_string( mailtext )
		if ADDHEADER and not message.has_key(encryptheader) and msg:
			message.add_header(encryptheader,msg)
		send_msg(message,from_addr,to_addr)
	except:
		debug("send_rawmsg: exception send_textmsg")
		send_textmsg(mailtext,from_addr,to_addr)

def send_msg( message,from_addr,to_addr ):
	global OUTPUT,mailcount
	debug("send_msg output %i"%OUTPUT)
	if type(message)==str:
		send_textmsg(message,from_addr,to_addr)
	else:
		send_textmsg(message.as_string(),from_addr,to_addr)

def send_textmsg(message, from_addr,to_addr):
	global OUTPUT,mailcount
	debug("send_textmsg output %i"%OUTPUT)

	if OUTPUT==o_mail:
		if len(to_addr) == 0:
			log("Couldn't send email, recipient list is empty!","e")
			return
		debug("Sending email to: <%s>" % to_addr)
		try:
			smtp = smtplib.SMTP(HOST, PORT)
			smtp.sendmail( from_addr, to_addr, message )
		except:
			log("Error sending email, smtp connection was not possible ''%(m1)s %(m2)s''"\
			%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
	
	
	elif OUTPUT==o_file and OUTFILE and len(OUTFILE)>0:
		try:
			fname=OUTFILE
			if mailcount>0:
				fname=OUTFILE+str(mailcount)
			f=open(fname,'w')
			f.write(message)
			f.close()
		except:
			log("Could not open Outputfile '%s'"%OUTFILE,"e")
			log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
			return
	else:
		print (message)
###################
#do_finally_at_exit
###################
def do_finally_at_exit():
	global logfile,tempfiles
	debug("do_finally")
	if RUNMODE==m_daemon:
		log("gpgmailencrypt daemon shutdown")
	for f in tempfiles:
		try:
			os.remove(f)
			debug("do_finally delete tempfile '%s'"%f)
		except:
			pass
	if LOGGING and logfile!=None:
		logfile.close()
###################################
#Definition of encryption functions
###################################
##########
#CLASS GPG
##########
GPGkeys=list()
class GPG:
	def __init__(self, keyhome=None, recipient = None):
		debug("GPG.__init__")
		if type(keyhome)==str:
			self._keyhome = expanduser(keyhome)
		else:
			self._keyhome=expanduser('~/.gnupg')
		self._recipient = ''
		self._filename=''	
		if type(recipient) == str:
			self.set_recipient(recipient)
		debug("GPG.__init__ end")

			
	def set_filename(self, fname):
		if type(fname)==str:
			self._filename=fname.strip()
		else:
			self._filename=''
	
	def set_keyhome(self,keyhome):
		if type(keyhome)==str:
			self._keyhome=expanduser(keyhome.strip())
		else:
			self._keyhome=''
		
	def set_recipient(self, recipient):
		if type(recipient) == str:
			self._recipient=recipient
			global GPGkeys
			GPGkeys = list()
	def recipient(self):
		return self._recipient	

	def public_keys(self):
		if len(GPGkeys)==0:
			self._get_public_keys()
		return GPGkeys

	def has_key(self,key):
		debug("gpg.has_key")
		if len(GPGkeys)==0:
			self._get_public_keys()
		if type(key)!=str:
			debug("has_key, key not of type str")
			return False
		if key in GPGkeys:	
			return True
		else:
			debug("has_key, key not in GPGkeys")
			debug("GPGkeys '%s'"%str(GPGkeys))
			return False
			
	def _get_public_keys( self ):
		global GPGkeys
		GPGkeys = list()
		cmd = '%s --homedir %s --list-keys --with-colons' % (GPGCMD, self._keyhome.replace("%user",self._recipient))
		debug("GPG.public_keys command: '%s'"%cmd)
		try:
			p = subprocess.Popen( cmd.split(' '), stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
			p.wait()
			for line in p.stdout.readlines():
				res=line.split(":")
				if res[0]=="pub" or res[0]=="uid":
					
					email=res[9]
					mail_id=res[4]
					try:
						found=re.search("[-a-zA-Z0-9_%\+\.]+@[-_0-9a-zA-Z\.]+\.[-_0-9a-zA-Z\.]+",email)
					except:
						log("re.exception reason '%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],
						"m2":sys.exc_info()[1]},"e")
					if found != None:
						try:
							email=email[found.start():found.end()]
						except:
							log("splitting email didn't work","e")
							email=""
						email=email.lower()
						if len(email)>0 and GPGkeys.count(email) == 0:
							#debug("add email address '%s'"%email)
							GPGkeys.append(email)
						#else:
							#debug("Email '%s' already added"%email)
		except:
			log("Error opening keyring (Perhaps wrong directory '%s'?)"%self._keyhome,"e")
			log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")

	def encrypt_file(self,filename=None,binary=False):
		global tempfiles,ALLOWGPGCOMMENT
		if filename:
			set_filename(filename)
		if len(self._filename) == 0:
			log( 'Error: GPGEncryptor: filename not set',"m")
			return ''
		f=new_tempfile()
		debug("GPG.encrypt_file new_tempfile %s"%f.name)
		f.close()
		_result = subprocess.call( ' '.join(self._command_fromfile(f.name,binary)),shell=True ) /256
		debug("Encryption command: '%s'" %' '.join(self._command_fromfile(f.name,binary)))
		if _result != 0:
			log("Error executing command (Error code %d)"%_result,"e")
		res=open(f.name)
		encdata=res.read()
		res.close()
		del_tempfile(f.name)
		return _result,encdata

	def _command_fromfile(self,sourcefile,binary):
		cmd=[GPGCMD, "--trust-model", "always", "-r",self._recipient,"--homedir", 
		self._keyhome.replace("%user",self._recipient), "--batch", "--yes", "--pgp7", "--no-secmem-warning", "--output",sourcefile, "-e",self._filename ]
		if ALLOWGPGCOMMENT==True:
			cmd.insert(1,"'%s'"%encryptgpgcomment)
			cmd.insert(1,"--comment")
		if not binary:
			cmd.insert(1,"-a")
		return cmd
#############################
#CLASS GPGENCRYPTEDATTACHMENT
#############################
class GPGEncryptedAttachment(email.message.Message):

    def  __init__(self):
    	email.message.Message. __init__(self)
    	self._masterboundary=None
    	self._filename=None
    	self.set_type("text/plain")

    def as_string(self, unixfrom=False):
        fp = StringIO()
        g = Generator(fp)
        g.flatten(self, unixfrom=unixfrom)
        return fp.getvalue()

    def set_filename(self,f):
    	self._filename=f

    def get_filename(self):
    	if self._filename != None:
    		return self._filename
    	else:
    		return email.message.Message.get_filename(self)

    def set_masterboundary(self,b):
    	self._masterboundary=b

    def _write_headers(self,g):
        print >> g._fp,'Content-Type: application/pgp-encrypted'
        print >> g._fp,'Content-Description: PGP/MIME version identification\n\nVersion: 1\n'
        print >>  g._fp,"--%s"%self._masterboundary
        fname=self.get_filename()
        if fname == None:
        	fname="encrypted.asc"
        print >> g._fp,'Content-Type: application/octet-stream; name="%s"'%fname
        print >> g._fp,'Content-Description: OpenPGP encrypted message'
        print >> g._fp,'Content-Disposition: inline; filename="%s"\n'%fname
############
#CLASS SMIME
############
class SMIME:
	def __init__(self, keyhome=None, recipient = None):
		global SMIMEKEYHOME
		debug("SMIME.__init__ %s"%SMIMEKEYHOME)
		if type(keyhome)==str:
			self._keyhome = expanduser(keyhome)
		else:
			self._keyhome=expanduser(SMIMEKEYHOME)
		self._recipient = ''
		self._filename=''	
		if type(recipient) == str:
			self._recipient=recipient
		debug("SMIME.__init__ end")

	def set_filename(self, fname):
		if type(fname)==str:
			self._filename=fname.strip()
		else:
			self._filename=''
	
	def set_keyhome(self,keyhome):
		if type(keyhome)==str:
			self._keyhome=expanduser(keyhome.strip())
		else:
			self._keyhome=''
		
	def set_recipient(self, recipient):
		if type(recipient) == str:
			self._recipient=recipient

	def recipient(self):
		return self._recipient	

	def has_key(self,key):
		debug("smime.has_key")
		global smimeuser
		if type(key)!=str:
			debug("smime has_key, key not of type str")
			return False
		try:
			_u=smimeuser[key]
		except:
			debug("smime has_key, key not found for '%s'"%key)
			return False
		return True

	def encrypt_file(self,filename=None,binary=False):
		global tempfiles
		if filename:
			set_filename(filename)
		if len(self._filename) == 0:
			log( 'Error: SMIME: filename not set',"m")
			return ''
		f=new_tempfile()
		debug("SMIME.encrypt_file new_tempfile %s"%f.name)
		f.close()
		_result = subprocess.call( ' '.join(self._command_fromfile(f.name,binary)),shell=True ) /256
		debug("Encryption command: '%s'" %' '.join(self._command_fromfile(f.name,binary)))
		if _result != 0:
			log("Error executing command (Error code %d)"%_result,"e")
		res=open(f.name)
		encdata=res.read()
		res.close()
		del_tempfile(f.name)
		m=email.message_from_string(encdata)
		return _result,m.get_payload()

	def _command_fromfile(self,sourcefile,binary):
		_recipient=smimeuser[self._recipient]
		encrypt="des3" # RFC 3583
		if _recipient[1]=="AES256":
			encrypt="aes-256-cbc"
		elif _recipient[1]=="AES128":
			encrypt="aes-128-cbc"
		elif _recipient[1]=="AES192":
			encrypt="aes-192-cbc"
		cmd=[SMIMECMD, "smime", "-%s" %encrypt,"-encrypt", "-in",self._filename,"-out", sourcefile,  _recipient[0] ]
		return cmd

	def opensslcmd(self,cmd):
		result=""
		p = subprocess.Popen( cmd.split(" "), stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
		result=p.stdout.read()
		return result, p.returncode

	def get_emailaddresses(self,certfile):
		cmd=[SMIMECMD,"x509","-in",certfile,"-text","-noout"]
		cert,returncode=self.opensslcmd(" ".join(cmd))
		email=[]
		found=re.search("(?<=emailAddress=)(.*)",cert)
		if found != None:
			try:
				email.append(cert[found.start():found.end()])
			except:
				pass
		found=re.search("(?<=email:)(.*)",cert) # get alias names
		if found != None:
			try:
				n=cert[found.start():found.end()]
				if n not in email:
					email.append(n)
			except:
				pass
		return email
	
	def get_fingerprint(self,cert):
		cmd=[SMIMECMD,"x509","-fingerprint","-in",cert,"-noout"]
		fingerprint,returncode=self.opensslcmd(" ".join(cmd))
		found= re.search("(?<=SHA1 Fingerprint=)(.*)",fingerprint)
		if found != None:
			try:
				fingerprint=fingerprint[found.start():found.end()]
			except:
				pass
		return fingerprint
	
	def extract_publickey_from_mail(self,mail,targetdir):
		debug("extract_publickey_from_mail to '%s'"%targetdir)
		f=tempfile.NamedTemporaryFile(mode='wb',delete=False,prefix='mail-')
		fname=f.name
		cmd=[SMIMECMD,"smime","-in", mail,"-pk7out","2>/dev/null","|",SMIMECMD,"pkcs7","-print_certs","-out",f.name,"2>/dev/null"]
		debug("extractcmd :'%s'"%" ".join(cmd))
		_result = subprocess.call( " ".join(cmd) ,shell=True) /256
		f.close()
		size=os.path.getsize(fname)
		if size==0:
			os.remove(fname)
			return None
		fp=self.get_fingerprint(fname)
		targetname="%s/%s.pem"%(targetdir,fp)
		self._copyfile(fname,targetname)
		os.remove(fname)
		return targetname
	
	def create_keylist(self,directory):
		result={}
		directory=expanduser(directory)
		try:
			_udir=os.listdir(directory)
		except:
			log("class SMIME.create_keylist, couldn't read directory '%s'"%directory)
			return result
		_match="^(.*?).pem"
		for _i in _udir:
			  if re.match(_match,_i):
			  	f="%s/%s"%(directory,_i)
			  	emailaddress=self.get_emailaddresses(f)
			  	if len(emailaddress)>0:
			  		for e in emailaddress:
			  			result[e] = [f,SMIMECIPHER]
		return result

	def verify_certificate(self,cert):
		cmd=[SMIMECMD,"verify",cert,"&>/dev/null"]
		_result = subprocess.call( " ".join(cmd) ,shell=True) /256
		return _result==0

	def _copyfile(self,src, dst):
		length=16*1024
		try:
			with open(expanduser(src), 'rb') as fsrc:
				with open(expanduser(dst), 'wb') as fdst:
				    	while 1:
				        	buf = fsrc.read(length)
				        	if not buf:
				            		break
	        				fdst.write(buf)
		except:
			log("Class smime._copyfile: Couldn't copy file, error '%(m1)s %(m2)s' occured!"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")	
#############
#is_encrypted
#############
def is_pgpinlineencrypted(msg):
	if msg ==None:
		return False
	if "\n-----BEGIN PGP MESSAGE-----" in msg and "\n-----END PGP MESSAGE-----" in msg:
		return True
	else:
		return False

def is_pgpmimeencrypted(msg):
	if type(msg)==str:
		msg=email.message_from_string(msg)
	contenttype=msg.get_content_type()
	if contenttype=="application/pgp-encrypted":
		return True
	else:
		return False
def is_smimeencrypted(msg):
	if type(msg)==str:
		msg=email.message_from_string(msg)
	contenttype=msg.get_content_type()
	if contenttype=="application/pkcs7-mime":
		return True
	else:
		return False

def is_encrypted(msg):
	if is_pgpmimeencrypted(msg) or is_pgpinlineencrypted(msg) or is_smimeencrypted(msg):
		return True
	else:
		return False
############
#decode_html
############
def decode_html(msg):
	h=htmldecode()
	h.feed(msg)
	return h.mydata()

htmlname={"Acirc":"Â","acirc":"â","acute":"´","AElig":"Æ","aelig":"æ","Agrave":"À","agrave":"à","alefsym":"ℵ","Alpha":"Α",
"alpha":"α","amp":"&","and":"∧","ang":"∠","apos":"'","Aring":"Å","aring":"å","asymp":"≈","Atilde":"Ã","atilde":"ã","Auml":"Ä",
"auml":"ä","bdquo":"„","Beta":"Β","beta":"β","brvbar":"¦","bull":"•","cap":"∩","Ccedil":"Ç","ccedil":"ç","cedil":"¸","cent":"¢",
"Chi":"Χ","chi":"χ","circ":"ˆ","clubs":"♣","cong":"≅","copy":"©","crarr":"↵","cup":"∪","curren":"¤","Dagger":"‡","dagger":"†",
"dArr":"⇓","darr":"↓","deg":"°","Delta":"Δ","delta":"δ","diams":"♦","divide":"÷","Eacute":"É","eacute":"é","Ecirc":"Ê",
"ecirc":"ê","Egrave":"È","egrave":"è","empty":"∅","emsp":" ","ensp":" ","Epsilon":"Ε","epsilon":"ε","equiv":"≡","Eta":"Η",
"eta":"η","ETH":"Ð","eth":"ð","Euml":"Ë","euml":"ë","euro":"€","exist":"∃","fnof":"ƒ","forall":"∀","frac12":"½","frac14":"¼",
"frac34":"¾","frasl":"⁄","Gamma":"Γ","gamma":"γ","ge":"≥","gt":">","hArr":"⇔","harr":"↔","hearts":"♥","hellip":"…","Iacute":"Í",
"iacute":"í","Icirc":"Î","icirc":"î","iexcl":"¡","Igrave":"Ì","igrave":"ì","image":"ℑ","infin":"∞","int":"∫","Iota":"Ι","iota":"ι",
"iquest":"¿","isin":"∈","Iuml":"Ï","iuml":"ï","Kappa":"Κ","kappa":"κ","Lambda":"Λ","lambda":"λ","lang":"⟨","laquo":"«","lArr":"⇐",
"larr":"←","lceil":"⌈","ldquo":"“","le":"≤","lfloor":"⌊","lowast":"∗","loz":"◊","lrm":"‎","lsaquo":"‹","lsquo":"‘","lt":"<",
"macr":"¯","mdash":"—","micro":"µ","middot":"·","minus":"−","Mu":"Μ","mu":"μ","nabla":"∇","nbsp":" ","ndash":"–","ne":"≠","ni":"∋",
"not":"¬","notin":"∉","nsub":"⊄","Ntilde":"Ñ","ntilde":"ñ","Nu":"Ν","nu":"ν","Oacute":"Ó","oacute":"ó","Ocirc":"Ô","ocirc":"ô",
"OElig":"Œ","oelig":"œ","Ograve":"Ò","ograve":"ò","oline":"‾","Omega":"Ω","omega":"ω","Omicron":"Ο","omicron":"ο","oplus":"⊕",
"or":"∨","ordf":"ª","ordm":"º","Oslash":"Ø","oslash":"ø","Otilde":"Õ","otilde":"õ","otimes":"⊗","Ouml":"Ö","ouml":"ö","para":"¶",
"part":"∂","permil":"‰","perp":"⊥","Phi":"Φ","phi":"φ","Pi":"Π","pi":"π","piv":"ϖ","plusmn":"±","pound":"£","Prime":"″","prime":"′",
"prod":"∏","prop":"∝","Psi":"Ψ","psi":"ψ","quot":'"',"radic":"√","rang":"⟩","raquo":"»","rArr":"⇒","rarr":"→","rceil":"⌉","rdquo":"”",
"real":"ℜ","reg":"®","rfloor":"⌋","Rho":"Ρ","rho":"ρ","rlm":"‏","rsaquo":"›","rsquo":"’","sbquo":"‚","Scaron":"Š","scaron":"š",
"sdot":"⋅","sect":"§","shy":"­","Sigma":"Σ","sigma":"σ","sigmaf":"ς","sim":"∼","spades":"♠","sub":"⊂","sube":"⊆","sum":"∑",
"sup":"⊃","sup1":"¹","sup2":"²","sup3":"³","supe":"⊇","szlig":"ß","Tau":"Τ","tau":"τ","there4":"∴","Theta":"Θ","theta":"θ",
"thetasym":"ϑ","thinsp":" ","THORN":"Þ","thorn":"þ","tilde":"˜","times":"×","trade":"™","Uacute":"Ú","uacute":"ú","uArr":"⇑",
"uarr":"↑","Ucirc":"Û","ucirc":"û","Ugrave":"Ù","ugrave":"ù","uml":"¨","upsih":"ϒ","Upsilon":"Υ","upsilon":"υ","Uuml":"Ü",
"uuml":"ü","weierp":"℘","Xi":"Ξ","xi":"ξ","Yacute":"Ý","yacute":"ý","yen":"¥","Yuml":"Ÿ","yuml":"ÿ","Zeta":"Ζ","zeta":"ζ",
"zwj":"‍","zwnj":"‌"
}
#class htmldecode
class htmldecode(HTMLParser.HTMLParser):
	def __init__(self):
		HTMLParser.HTMLParser.__init__(self)
		self.data=""
		self.in_throwaway=0
		self.in_keep=0
		self.first_td_in_row=False
		self.dbg=False
		self.abbrtitle=None

	def get_attrvalue(self,tag,attrs):
		if attrs==None:
			return None
		for i in attrs:
			if len(i)<2:
				return None
			if i[0]==tag:
				return i[1]
		return None
				
	def handle_starttag(self, tag, attrs):
		if self.dbg:
			debug( "<%s>"%tag)
		self.handle_tag(tag,attrs)

	def handle_entityref(self, name):
		c = ""
		e=None
		try:
			e=htmlname[name]
		except:
			pass
		if e:
			c=e
		else:
			c="_%s_"%w

		self.data+=c

	def handle_endtag(self, tag):
		if self.dbg:
			debug("</%s>"%tag)
		self.handle_tag(tag,starttag=False)

	def handle_startendtag(self,tag,attrs):
		if self.dbg:
			debug("< %s/>"%tag)
		if tag=="br":
			self.handle_tag(tag,attrs,starttag=False)

	def handle_data(self, data):
		if self.in_throwaway==0:
			if self.dbg:
				debug("   data: '%s'"%data)
			if self.in_keep>0:
				self.data+=data
			elif len(data.strip())>0:
				self.data+=data.replace("\n","").replace("\r\n","")

	def handle_charref(self, name):
		if self.dbg:
			debug("handle_charref '%s'"%name)
		if name.startswith('x'):
			c = chr(int(name[1:], 16))
		else:
			c = chr(int(name))
		self.data+=c
 
	def handle_tag(self,tag,attrs=None,starttag=True):
		if tag in ("style","script","title"):
			if starttag:
				self.in_throwaway+=1
			else:
				if self.in_throwaway>0:		
					self.in_throwaway-=1
		if tag=="pre":
			if starttag:
				self.in_keep+=1
			else:
				if self.in_keep>0:		
					self.in_keep-=1
		if tag=="br":
			self.data+="\r\n"
		if len(self.data)>0:
			lastchar=self.data[len(self.data)-1]
		else:
			lastchar=""
		if tag=="hr":
			if lastchar!="\n":
				self.data+="\r\n"
			self.data+="=========================\r\n"
		if starttag:
			#Starttag
			if tag=="table":
				if lastchar!="\n":
					self.data+="\r\n"
			if tag=="tr":
				self.first_td_in_row=True
				if self.dbg:
					debug("tr first_td_in_row=True")
			if tag in ("td","th") :
				if self.dbg:
					debug("<td/th> first %s"%self.first_td_in_row)
				if  not self.first_td_in_row:
					if self.dbg:
						debug("     td/th \\t")
					self.data+="\t"
				else:
					self.first_td_in_row=False
			if tag in ("li"):
				self.data+="\r\n * "
			if tag=="q":
				self.data+="\""		
			if tag=="abbr":
				self.attrtitle=self.get_attrvalue("title",attrs)
		else:
			#Endtag
			if tag in("h1","h2","h3","h4","h5","h6","title","p","ol","ul","caption") and lastchar not in ("\n"," ","\t"):
				self.data+="\r\n"
			if tag=="tr":
				if lastchar=="\t":
					self.data=self.data[0:len(self.data)-1]
					self.data+="\r\n"
				else:
					if lastchar not in ("\n"," ","\t"):
						self.data+="\r\n"
			if tag=="abbr" and self.attrtitle!=None:
				self.data+=" [%s] "%self.attrtitle
				self.attrtitle=None
	def mydata(self):
		return self.data
###########
#split_html
###########
def split_html(html):
	_r=re.sub(r"(?ims)<STYLE(.*?)</STYLE>","",html)
	res=re.search('(?sim)<BODY(.*?)>',_r,re.IGNORECASE)
	result=False
	body=""
	header=""
	footer=""
	if res:
		result=True		
		header=_r[0:res.end()]
		body=_r[res.end():]
		footer=""
		res=re.search('(?sim)</BODY(.*?)>',body,re.IGNORECASE)
		if res:
			footer=body[res.start():]
			body=decode_html(body[0:res.start()])
	else:		
		body=decode_html(_r)
	return result,header,body,footer
####################
#guess_fileextension
####################
def guess_fileextension(ct):
	try:
		maintype,subtype=ct.split("/")
	except:
		maintype=ct
		subtype="plain"
	if maintype=="image":
		if subtype in ("jpeg","pjpeg"):
			return "jpg"
		elif subtype=="svg+xml":
			return "svg"
		elif subtype in ("tiff","x-tiff"):
			return "tif"
		elif subtype=="x-icon":
			return "ico"
		elif subtype=="vnd.djvu":
			return "dvju"
		return subtype
	if maintype=="audio":
		if subtype=="basic":
			return "au"
		if subtype in ("vnd.rn-realaudio","x-pn-realaudio"):
			return "ra"
		elif subtype in ("vnd.wave","x-wav"):
			return "wav"
		elif subtype in ("midi","x-midi"):
			return "mid"
		elif subtype=="x-mpeg":
			return "mp2"
		elif subtype in ("mp3","mpeg","ogg","midi"):
			return subtype
	if maintype=="video":
		if subtype=="x-ms-wmv":
			return "wmv"
		elif subtype=="quicktime":
			return "mov"
		elif subtype in ("x-matroska"):
			return "mkv"
		elif subtype in ("x-msvideo"):
			return "avi"
		elif subtype in ("avi","mpeg","mp4","webm"):
			return subtype
	if maintype=="application":
		if subtype in ("javascript","x-javascript","ecmascript"):
			return "js"
		elif subtype=="postscript":
			return "ps"
		elif subtype in ("pkcs10","pkcs-10","x-pkcs10"):
			return "p10"
		elif subtype in ("pkcs12","pkcs-12","x-pkcs12"):
			return "p12"
		elif subtype in ("x-pkcs7-mime","pkcs7-mime"):
			return "p7c"
		elif subtype in ("x-pkcs7-signature","pkcs7-signature"):
			return "p7a"
		elif subtype=="x-shockwave-flash":
			return "swf"
		elif subtype=="mswrite":
			return "wri"
		elif subtype in ("msexcel","excel","vnd.ms-excel","x-excel","x-msexcel"):
			return "xls"
		elif subtype in ("msword","word","vnd.ms-word","x-word","x-msword"):
			return "doc"
		elif subtype in ("mspowerpoint","powerpoint","vnd.ms-powerpoint","x-powerpoint","x-mspowerpoint"):
			return "ppt"
		elif subtype in ("gzip","x-gzip","x-compressed"):
			return "gz"
		elif subtype=="x-bzip2":
			return "bz2"
		elif subtype=="x-gtar":
			return "gtar"
		elif subtype=="x-tar":
			return "tar"
		elif subtype=="x-dvi":
			return "dvi"
		elif subtype=="x-midi":
			return "mid"
		elif subtype in("x-lha","lha"):
			return "lha"
		elif subtype in("x-rtf","rtf","richtext"):
			return "rtf"
		elif subtype=="x-httpd-php":
			return "php"
		elif subtype in ("atom+xml","xhtml+xml","xml-dtd","xop+xml","soap+xml","rss+xml","rdf+xml","xml"):
			return "xml"
		elif subtype in ("arj","lzx","json","ogg","zip","gzip","pdf","rtc"):
			return subtype
	if maintype=="text":
		if subtype in ("plain","cmd","markdown"):
			return "txt"
		elif subtype=="javascript":
			return "js"
		elif subtype in ("comma-separated-values","csv"):
			return "csv"
		elif subtype in ("vcard","x-vcard","directory;profile=vCard","directory"):
			return "vcf"
		elif subtype=="tab-separated-values":
			return "tsv"
		elif subtype=="uri-list":
			return "uri"
		elif subtype=="x-c":
			return "c"
		elif subtype=="x-h":
			return "h"
		elif subtype=="x-vcalendar":
			return "vcs"
		elif "x-script" in subtype:
			r=subtype.split(".")
			if len(r)==2:
				return r[1]
			else:
				return "hlb"
		elif subtype in ("asp","css","html","rtf","xml"):
			return subtype
	e=mimetypes.guess_extension(ct)
	if e:
		e=e.replace(".","")
		debug("guess_fileextension '%s'=>'%s'"%(ct,e))
		return e
	else:
		return "bin"
##########
#asciiname
##########
def asciiname(name):
	return re.sub(r'[^\x00-\x7F]','_', name)
################
#encrypt_payload
################
def encrypt_payload( payload,gpguser,counter=0 ):
	debug("encrypt_payload")
	global tempfiles
	htmlheader=""
	htmlbody=""
	htmlfooter=""
	gpg = GPG( GPGKEYHOME, gpguser)
	raw_payload = payload.get_payload(decode=True)
	contenttype=payload.get_content_type()		
	debug("Content-Type:'%s'"%contenttype)
	fp=new_tempfile()
	debug("encrypt_payload new_tempfile %s"%fp.name)
	filename = payload.get_filename()
	if contenttype=="text/html":
		res,htmlheader,htmlbody,htmlfooter=split_html(raw_payload)
		payload.set_charset("UTF-8")
		fp.write(htmlbody)
	else:
		fp.write(raw_payload)
	fp.close()
	isAttachment = payload.get_param( 'attachment', None, 'Content-Disposition' ) is not None
	isInline=payload.get_param( 'inline', None, 'Content-Disposition' ) is not None
	gpg.set_filename( fp.name )
	if is_encrypted(raw_payload):
		if ADDHEADER:
			if not payload.has_key(encryptheader):
				payload[encryptheader] = 'Mail was already encrypted'
			debug("Mail was already encrypted")
		if len(OUTFILE) >0:
			return None	
		del_tempfile(fp.name)
		return payload
	contentmaintype=payload.get_content_maintype() 
	if isAttachment or (isInline and contentmaintype not in ("text") ):
		addPGPextension=True
		if filename==None:
			count=""
			if counter>0:
				count="%i"%counter
			filename=('%s%s.'%(LOCALEDB[LOCALE][1],count))+guess_fileextension(contenttype)
		else:
			filename=asciiname(filename)
			f,e=os.path.splitext(filename)
			addPGPextension=(e.lower()!=".pgp")
		debug("Filename:'%s'"%filename)
		isBinaryattachment=(contentmaintype!="text")
		if addPGPextension:
			result,pl=gpg.encrypt_file(binary=isBinaryattachment)
		else:
			result=1
		if result==0:
			payload.set_payload(pl)
			if filename and addPGPextension:
				pgpFilename = filename + ".pgp"
			else:
				pgpFilename=filename
			payload.set_type( 'application/octet-stream')
			if isBinaryattachment:
				Encoders.encode_base64(payload)
			else:
				if payload.has_key('Content-Transfer-Encoding'):
					del payload['Content-Transfer-Encoding']
				payload["Content-Transfer-Encoding"]="8bit"

			if payload["Content-Disposition"]:
				del payload["Content-Disposition"]
			payload.add_header('Content-Disposition', 'attachment; filename="%s"' % pgpFilename)
			payload.set_param( 'name', pgpFilename )
	else:
		if payload.has_key('Content-Transfer-Encoding'):
			del payload['Content-Transfer-Encoding']
		payload["Content-Transfer-Encoding"]="8bit"
		result,pl=gpg.encrypt_file(binary=False) 
		if result==0:
			if contenttype=="text/html":
				pl=htmlheader+"\n<br>\n"+re.sub('\n',"<br>\n",pl)+"<br>\n"+htmlfooter
			payload.set_payload(pl)
		else:
			log("Error during encryption: payload will be unencrypted!","m")	
	del_tempfile(fp.name)
	debug("encrypt_payload ENDE")
	return payload
##################
#encrypt_pgpinline
##################
def encrypt_pgpinline(mail,gpguser,from_addr,to_addr):
	debug("encrypt_pgpinline")
	message=email.message_from_string(mail)
	counter=0
	attach_list=list()
	appointment="appointment"
	try:
		appointment=LOCALEDB[LOCALE][0]
	except:
		pass
	cal_fname="%s.ics.pgp"%appointment
	if type (message) == list:
		msg=message
	else:
		msg=message.walk()
		contenttype=message.get_content_type()	
		debug("CONTENTTYPE %s"%contenttype)
		if type( message.get_payload() ) == str:
			debug("encrypt_pgpinlie: type( message.get_payload() ) == str")
			pl=encrypt_payload( message ,gpguser)
			if contenttype=="text/calendar":
				CAL=MIMEText(pl.get_payload(decode=True),_subtype="calendar",_charset="UTF-8")
				CAL.add_header('Content-Disposition', 'attachment', filename=cal_fname)
				CAL.set_param( 'name', cal_fname)
				pl.set_payload(None)
				pl.set_type("multipart/mixed")
				pl.attach(CAL)
			debug("encrypt_pgpinlie: type( message.get_payload() ) == str ENDE")
			return pl
	for payload in msg:
		content=payload.get_content_maintype()
                if (content in ("application","image","audio","video" )) \
                and payload.get_param( 'inline', None, 'Content-Disposition' ) is None:
                	payload.add_header('Content-Disposition', 'attachment;"')
		if payload.get_content_maintype() == 'multipart':
			continue
		if( type( payload.get_payload() ) == list ):
			continue
		else:
			res=encrypt_payload( payload,gpguser,counter )
			if res and payload.get_content_type()=="text/calendar" and payload.get_param( 'attachment', None, 'Content-Disposition' ) is  None:

				CAL=MIMEText(res.get_payload(decode=True),_subtype="calendar",_charset="UTF-8")
				CAL.add_header('Content-Disposition', 'attachment', filename=cal_fname)
				CAL.set_param( 'name', cal_fname)
				payload.set_payload("")
				payload.set_type("text/plain")
				attach_list.append(CAL)
        	        if (content in ("application","image","audio","video" )):
 				counter+=1
	for a in attach_list:
		message.attach(a)
	debug("encrypt_pgpinline ENDE")
	return message
################
#encrypt_pgpmime
################
def encrypt_pgpmime(message,gpguser,from_addr,to_addr):
	global tempfiles
	debug("encrypt_pgpmime")
	raw_message=email.message_from_string(message)
	splitmsg=re.split("\n\n",message,1)
	if len(splitmsg)!=2:
		splitmsg=re.split("\r\n\r\n",message,1)
	if len(splitmsg)!=2:
		log("Mail could not be split in header and body part (mailsize=%i)"%len(message),"e")
		send_rawmsg(message,"Error parsing email",from_addr,to_addr)
		return None
	header,body=splitmsg 
	header+="\n\n"

	try:
		newmsg=email.message_from_string( header)
	except:
		log("creating new message failed","w")
		log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")

	contenttype="text/plain"
	contenttransferencoding=None
	contentboundary=None
	c=newmsg.get("Content-Type")

	if c==None:
		debug("Content-Type not set, set default 'text/plain'.")
		newmsg.set_type("text/plain")

	boundary=make_boundary(message)

	try:
		newmsg.set_boundary(boundary)
	except:
		log("Error setting boundary: %(m1)s %(m2)s"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]})

	res= re.search("boundary=.*\n",message,re.IGNORECASE)
	if res:
		_b=message[res.start():res.end()]
		res2=re.search("\".*\"", _b)
		if res2:
			contentboundary=_b[(res2.start()+1):(res2.end()-1)]
	try:
		contenttype=newmsg.get_content_type()
		debug("Content-Type:'%s'"%str(contenttype))
		contenttransferencoding=newmsg['Content-Transfer-Encoding']
	except:
		log("contenttype and/or transerfencoding could not be found")
		log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")

	newmsg.set_type("multipart/encrypted")
	newmsg.set_param("protocol","application/pgp-encrypted")
	newmsg.preamble='This is an OpenPGP/MIME encrypted message (RFC 4880 and 3156)'

	if newmsg.has_key('Content-Transfer-Encoding'):
		del newmsg['Content-Transfer-Encoding']

	gpg = GPG( GPGKEYHOME, gpguser)
	fp=new_tempfile()
	debug("encrypt_mime new tempfile %s"%fp.name)
	if contenttype ==None:
		contenttype="multipart/mixed"
	protocol=""
	if contenttype=="multipart/signed":
		protocol=" protocol=\"application/pgp-signature\";\n"
	msgheader='Content-Type: %(ctyp)s;\n%(protocol)s boundary="%(bdy)s"\n'\
		%{"bdy":contentboundary,"ctyp":contenttype,"protocol":protocol}
	if contenttransferencoding !="None":
		msgheader+=("Content-Transfer-Encoding: %s\n" %contenttransferencoding)
	bodymsg=email.message.Message()
	if "multipart" in contenttype:
		bodymsg["Content-Type"]=contenttype
	else:	
		bodymsg["Content-Type"]="multipart/mixed"
	if contenttransferencoding!="None" and contenttransferencoding!=None and len(contenttransferencoding)>0:
		bodymsg["Content-Transfer-Encoding"]=contenttransferencoding
	rawpayload=raw_message.get_payload()
	if type(rawpayload) == str:
		debug("Payload==String len=%i"%len(rawpayload))
		if contenttype ==None:
			contenttype="multipart/mixed"
		protocol=""
		charset=""
		if contenttype=="multipart/signed":
			protocol=" protocol=\"application/pgp-signature\";\n"
		_ch=find_charset(header)
		debug("Charset:%s"%str(_ch))
		bdy=""
		if contentboundary!=None:
			bdy='boundary="%s"\n'%contentboundary
		if ("text/" in contenttype) and _ch!= None and len(_ch)>0 :
			charset="charset=\"%s\""%_ch
			debug("content-type: '%s' charset: '%s'"%(contenttype,charset))
		msgheader='Content-Type: %(ctyp)s; %(charset)s\n%(protocol)s%(bdy)s'\
		%{"bdy":bdy,"ctyp":contenttype,"protocol":protocol,"charset":charset}
		debug("msgheader:    '%s'"%str(msgheader))
		debug("new boundary: '%s'"%str(boundary))
		if contenttransferencoding !=None:
			msgheader+=("Content-Transfer-Encoding: %s\n" %contenttransferencoding)
		body=msgheader+"\n"+body	
	else:
		debug("Payload==Msg")
		for p in rawpayload:
			bodymsg.attach(p)
		body=bodymsg.as_string()	
	fp.write(body)
	fp.close()
	gpg.set_filename( fp.name )
	attachment=GPGEncryptedAttachment()
	if is_encrypted(message):
		send_rawmsg(message,'Mail was already encrypted',from_addr,to_addr)
		del_tempfile(fp)
		return None
	result,pl=gpg.encrypt_file(binary=False) 
	if result==0:
		attachment.set_payload(pl)
	else:
		log("Error during encryption pgpmime: payload will be unencrypted!","m")	
	newmsg.set_payload(attachment)
	newmsg.set_boundary(boundary)
	attachment.set_boundary(contentboundary)
	attachment.set_masterboundary(boundary)
	debug("encrypt_pgpmime END")
	del_tempfile(fp.name)
	return newmsg

#####################
#check_gpgprecipients
#####################
def check_gpgrecipient(gaddr):
	global DOMAINS
	debug("check_gpgrecipient: start '%s'"%gaddr)
	addr=gaddr.split('@')
	domain=''
	if len(addr)==2:
		domain = gaddr.split('@')[1]
	found =False
	gpg = GPG( GPGKEYHOME)
	try:
		gpg_to_addr=addressmap[gaddr]
	except:
		debug("addressmap to_addr not found")
		gpg_to_addr=gaddr
	else:
		found =True

	if gpg.has_key(gaddr):
		if (len(DOMAINS)>0 and domain in DOMAINS.split(',')) or len(DOMAINS)==0:
			found=True
			debug("check_gpgrecipient: after in_key")
		else:
			debug("gpg key exists, but '%s' is not in DOMAINS [%s]"%(domain,DOMAINS))
	debug("check_gpgrecipient: end")
	return found,gpg_to_addr
##############################
#get_preferredencryptionmethod
##############################	
def get_preferredencryptionmethod(user):
	debug("get_preferredencryptionmethod :'%s'"%user)
	global PREFER_GPG,PGPMIME
	method=""
	if PREFER_GPG:
		if PGPMIME:
			method="PGPMIME"
		else:
			method="PGPINLINE"
	else:
		method="SMIME"
	_m=""
	_u=user
	try:
		_u=addressmap[user]
	except:
		pass
	try:
		_m=encryptionmap[_u].upper()
	except:
		debug("get_preferredencryptionmethod User '%s' not found"%user)
		return method
	if _m in ("PGPMIME","PGPINLINE","SMIME","NONE"):
		debug("get_preferredencryptionmethod User %s (=> %s) :'%s'"%(user,_u,_m))
		return _m
	else:
		debug("get_preferredencryptionmethod: Method '%s' for user '%s' unknown" % (_m,_u))
		return method
#################
#encrypt_gpg_mail 
#################
def encrypt_gpg_mail(mailtext,use_pgpmime, gpguser,from_addr,to_addr):
	raw_message=email.message_from_string(mailtext)
	m_id=""
	if raw_message.has_key("Message-Id"):
		m_id="Id:%s "%raw_message["Message-Id"]
	log("Encrypting email %s to: %s" % (m_id, to_addr) )
	if raw_message.has_key("Subject") and len(SPAMSUBJECT.strip())>0 and SPAMSUBJECT in raw_message["Subject"]:
		debug("message is SPAM, don't encrypt")
		send_rawmsg(mailtext,"Spammail",from_addr,to_addr)
		return
	if is_smimeencrypted( mailtext ) or is_pgpmimeencrypted(mailtext):
		debug("encrypt_gpg_mail, is already smime or pgpmime encrypted")
		send_rawmsg(mailtext,'Mail was already encrypted',from_addr,to_addr)
		return
	
	if use_pgpmime:
		mail = encrypt_pgpmime( mailtext,gpguser,from_addr,to_addr )
	else:
		#PGP Inline
		mail = encrypt_pgpinline( mailtext,gpguser,from_addr,to_addr )
	if mail==None:
		return
	debug("vor sendmsg")
	send_msg( mail, from_addr, to_addr )
#####################
#check_smimerecipient
#####################
def check_smimerecipient(saddr):
	global DOMAINS,SMIMEKEYHOME
	debug("check_smimerecipient: start")
	addr=saddr.split('@')
	domain=''
	if len(addr)==2:
		domain = saddr.split('@')[1]
	found =False
	smime = SMIME(SMIMEKEYHOME)
	try:
		smime_to_addr=addressmap[saddr]
	except:
		debug("smime addressmap to_addr not found")
		smime_to_addr=saddr
	debug("check_smimerecipient '%s'"%smime_to_addr)
	if smime.has_key(smime_to_addr):
		found=True
		debug("check_smimerecipient FOUND") 
		if (len(DOMAINS)>0 and domain in DOMAINS.split(',')) or len(DOMAINS)==0:
			debug("check_smimerecipient: after in_key")
		else:
			debug("smime key exists, but '%s' is not in DOMAINS [%s]"%(domain,DOMAINS))
			found=False
	return found, smime_to_addr
####################
# encrypt_smime_mail 
####################
def encrypt_smime_mail(mailtext,smimeuser,from_addr,to_addr):
	debug("encrypt_smime_mail")
	raw_message=email.message_from_string(mailtext)
	global tempfiles
	contenttype="text/plain"
	contenttransferencoding=None
	contentboundary=None
	if is_smimeencrypted(mailtext) or is_pgpmimeencrypted(mailtext):
		log("encrypt_smime_mail:mail is already smime or pgpmime encrypted")
		send_rawmsg(mailtext,"Mail was already encrypted",from_addr,to_addr)
		return
		
	splitmsg=re.split("\n\n",mailtext,1)
	if len(splitmsg)!=2:
		splitmsg=re.split("\r\n\r\n",mailtext,1)
	if len(splitmsg)!=2:
		log("Mail could not be split in header and body part (mailsize=%i)"%len(mailtext),"e")
		send_rawmsg(mailtext,"Not encrypted",from_addr,to_addr)
		return
	header,body=splitmsg 
	header+="\n\n"
	try:
		newmsg=email.message_from_string( header)
	except:
		log("creating new message failed","w")
		log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
		return 
	m_id=""
	if raw_message.has_key("Message-Id"):
		m_id="Id:%s "%raw_message["Message-Id"]
	log("Encrypting email %s to: %s" % (m_id, to_addr) )

	res= re.search("boundary=.*\n",mailtext,re.IGNORECASE)
	if res:
		_b=mailtext[res.start():res.end()]
		res2=re.search("\".*\"", _b)
		if res2:
			contentboundary=_b[(res2.start()+1):(res2.end()-1)]
	try:
		contenttype=newmsg.get_content_type()
		debug("Content-Type:'%s'"%str(contenttype))
		contenttransferencoding=newmsg['Content-Transfer-Encoding']
	except:
		log("contenttype and/or transerfencoding could not be found")
		log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
	newmsg.set_type( 'application/pkcs7-mime')
	if newmsg["Content-Disposition"]:
		del newmsg["Content-Disposition"]
	newmsg.add_header('Content-Disposition', 'attachment; filename="smime.p7m"')
	newmsg.set_param( 'smime-type', 'enveloped-data',requote=False)
	newmsg.set_param( 'name', 'smime.p7m')
	newmsg.del_param("charset")
	newmsg.del_param("boundary")
	protocol=newmsg.get_param("protocol")
	newmsg.del_param("protocol")
	if newmsg["Content-Transfer-Encoding"]:
		del newmsg["Content-Transfer-Encoding"]
	newmsg.add_header('Content-Transfer-Encoding', 'base64')
	smime = SMIME( SMIMEKEYHOME)
	smime.set_recipient(smimeuser)
	fp=new_tempfile()
	debug("encrypt_smime_mail new_tempfile %s"%fp.name)
	bodymsg=email.message.Message()
	if "multipart" in contenttype:
		bodymsg["Content-Type"]=contenttype
	else:	
		bodymsg["Content-Type"]="multipart/mixed"
	if protocol:
		bodymsg.set_param("Protocol",protocol)
	if contenttransferencoding!="None" and contenttransferencoding!=None and len(contenttransferencoding)>0:
		bodymsg["Content-Transfer-Encoding"]=contenttransferencoding
	rawpayload=raw_message.get_payload()
	if type(rawpayload) == str:
		debug("Payload==String len=%i"%len(rawpayload))
		if contenttype ==None:
			contenttype="multipart/mixed"
		protocol=""
		charset=""
		if contenttype=="multipart/signed":
			protocol=" protocol=\"application/pgp-signature\";\n"
		_ch=find_charset(header)
		debug("Charset:%s"%str(_ch))
		bdy=""
		if contentboundary!=None:
			bdy='boundary="%s"\n'%contentboundary
		if ("text/" in contenttype) and _ch!= None and len(_ch)>0 :
			charset="charset=\"%s\""%_ch
			debug("content-type: '%s' charset: '%s'"%(contenttype,charset))
		msgheader='Content-Type: %(ctyp)s; %(charset)s\n%(protocol)s%(bdy)s'\
		%{"bdy":bdy,"ctyp":contenttype,"protocol":protocol,"charset":charset}
		debug("msgheader:    '%s'"%str(msgheader))
		if contenttransferencoding !=None:
			msgheader+=("Content-Transfer-Encoding: %s\n" %contenttransferencoding)
		body=msgheader+"\n"+body	
	else:
		debug("Payload==Msg")
		for p in rawpayload:
			bodymsg.attach(p)
		body=bodymsg.as_string()	
	fp.write(body)
	fp.close()
	smime.set_filename(fp.name)
	result,pl=smime.encrypt_file()
	if result==0:
		debug("encrypt_smime_mail: send encrypted mail")
		if ADDHEADER:
			if newmsg.has_key(encryptheader):
				del newmsg[encryptheader]
			newmsg[encryptheader] = encryptgpgcomment
		newmsg.set_payload( pl )
		send_msg( newmsg,from_addr,to_addr )
	else:
		debug("encrypt_smime_mail: error encrypting mail, send unencrypted")
		m=None
		send_rawmsg(mailtext,m,from_addr,to_addr)
	del_tempfile(fp.name)
###############
# encrypt_mails 
###############
def encrypt_mails(mailtext,receiver):
	global mailcount,PREFER_GPG,PGPMIME
	debug("encrypt_mails")
	_pgpmime=PGPMIME
	if SMIMEAUTOMATICEXTRACTKEYS:
		debug("SMIMEAUTOMATICEXTRACTKEYS")
		f=new_tempfile()
		f.write(mailtext)
		f.close()
		s=SMIME(SMIMEKEYHOME)
		s.extract_publickey_from_mail(f.name,SMIMEKEYEXTRACTDIR)
		del_tempfile(f.name)
	for to_addr in receiver:
		debug("encrypt_mail for user '%s'"%to_addr)
		g_r,to_gpg=check_gpgrecipient(to_addr)
		s_r,to_smime=check_smimerecipient(to_addr)
		method=get_preferredencryptionmethod(to_addr)
		debug("GPG encrypt possible %i"%g_r)
		debug("SMIME encrypt possible %i"%s_r)
		if method=="PGPMIME":
			_prefer_gpg=True
			_pgpmime=True
		elif method=="PGPINLINE":
			_prefer_gpg=True
			_pgpmime=False
		if method=="SMIME":
			_prefer_gpg=False
		if method=="NONE":
			g_r=False
			s_r=False
		try:
			raw_message = email.message_from_string( mailtext )
		except:
			log("Exception creating raw_message in '%(m1)s %(m2)s'occured!"\
			%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
			return
		from_addr = raw_message['From']
		if not s_r and not g_r:
			m="Email not encrypted, public key for '%s' not found"%to_addr
			log(m,"w")
			send_rawmsg(mailtext,m,from_addr,to_addr)
			continue
		if _prefer_gpg:
			debug("PREFER GPG")
			if g_r:
				encrypt_gpg_mail(mailtext,_pgpmime,to_gpg,from_addr,to_addr)
			else:
				encrypt_smime_mail(mailtext,to_smime,from_addr,to_addr)
		else:
			debug("PREFER SMIME")
			if s_r:
				encrypt_smime_mail(mailtext,to_smime,from_addr,to_addr)
			else:
				encrypt_gpg_mail(mailtext,_pgpmime,to_gpg,from_addr,to_addr)
		mailcount+=1
			
	debug("END encrypt_mails")
#######################################
#END definition of encryption functions
#######################################
###########
#scriptmode
###########
def scriptmode():
	try:
		#read message
		if len(INFILE)>0:
			try:
				f=open(INFILE)
				raw=f.read()
				f.close()
			except:
				log("Could not open Inputfile '%s'"%INFILE,"e")
				log("'%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
				exit(2)
		else:
			raw = sys.stdin.read()

		if debug_keepmail(raw): #DEBUG
			DEBUG=True
			f=tempfile.NamedTemporaryFile(mode='wb',delete=False,prefix='mail-')
			f.write(raw)
			f.close()
			log("Message in temporary file '%s'"%f.name)

		#do the magic
		encrypt_mails(raw,receiver)
	except SystemExit,m:
		debug("Exitcode:'%s'"%m)
		exit(int(m.code))
	except:
	  	log("Bug:Exception in '%(m1)s %(m2)s' occured!"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
	  	exit(4)	
	else:
		debug("Program exits without errors")
		exit(0)	
###########
#daemonmode
###########
def daemonmode():
	import smtpd,asyncore, signal
	signal.signal(signal.SIGTERM, sigtermhandler)
	signal.signal(signal.SIGHUP,  sighuphandler)
	log("gpgmailencrypt starts as daemon on %s:%s"%(SERVERHOST,SERVERPORT) )
	class gpgmailencryptserver(smtpd.SMTPServer):
		def process_message(self, peer, mailfrom, receiver, data):
			debug("gpgmailencryptserver from '%s' to '%s'"%(mailfrom,receiver))
			encrypt_mails(data,receiver)
			return
	try:
		server = gpgmailencryptserver((SERVERHOST, SERVERPORT), None)
	except:
		log("Couldn't start mail server '%(m1)s %(m2)s'"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
		exit(1)
	try:
		asyncore.loop()
	except SystemExit,m:
		exit(0)
	except:
	  	log("Bug:Exception in '%(m1)s %(m2)s' occured!"%{"m1":sys.exc_info()[0],"m2":sys.exc_info()[1]},"e")
###############
#sigtermhandler
###############
def sigtermhandler(signum, frame):
		exit(0)
###############
#sigthuphandler
###############
def sighuphandler(signum, frame):
	log("Signal SIGHUP: reload configuration")
	init()
	read_configfile()
##############################
# gpgmailencrypt main program
##############################
init()
read_configfile()
if __name__ == "__main__":
	receiver=parse_commandline()
	set_logmode()
	debug("after parse_commandline %s"%SMIMEKEYHOME)
	if RUNMODE==m_daemon:
		daemonmode()
	else:
		scriptmode()

