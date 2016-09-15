#License GPL v3
#Author Horst Knorr <gpgmailencrypt@gmx.de>
from gmeutils.child 			import _gmechild
from gmeutils.helpers			import *
from gmeutils.version			import *
from gmeutils._dbg 				import _dbg
import os.path
import time

__all__ =["get_backend","get_backendlist"]

##############
#_base_storage
##############

class _base_storage(_gmechild):

	def __init__(self,parent,backend):
		_gmechild.__init__(self,parent=parent,filename=__file__)
		self._backend=backend
		self.init()

	#####
	#init
	#####

	@_dbg
	def init(self):
		pass

	################
	#read_configfile
	################

	@_dbg
	def read_configfile(self,cfg):
		raise NotImplementedError

	########
	#usermap
	########

	@_dbg
	def usermap(self, user):
		raise NotImplementedError

	##############
	#encryptionmap
	##############

	@_dbg
	def encryptionmap(self, user):
		raise NotImplementedError

	##########
	#smimeuser
	##########

	@_dbg
	def smimeuser(self, user):
		raise NotImplementedError

	#################
	#smimepublic_keys
	#################

	@_dbg
	def smimepublic_keys(self):
		raise NotImplementedError

	##################
	#smimeprivate_keys
	##################

	@_dbg
	def smimeprivate_keys(self):
		raise NotImplementedError

	################
	#set_pdfpassword
	################

	@_dbg
	def set_pdfpassword(self,user,password,autodelete=True):
		raise NotImplementedError

	################
	#get_pdfpassword
	################

	@_dbg
	def get_pdfpassword(self,user):
		raise NotImplementedError

	###################
	#reset_pdfpasswords
	###################

	@_dbg
	def reset_pdfpasswords(self):
		raise NotImplementedError

	#####################
	#del_old_pdfpasswords
	#####################

	@_dbg
	def del_old_pdfpasswords(self,age):
		raise NotImplementedError

##############
#_TEXT_BACKEND
##############

class _TEXT_BACKEND(_base_storage):

	#####
	#init
	#####

	@_dbg
	def init(self):
		self._addressmap = dict()
		self._encryptionmap = dict()
		self._smimeuser = dict()
		self._pdfpasswords=dict()
		self._PDF_PASSWORDFILE="/etc/gpgpdfpasswords.pw"

	################
	#read_configfile
	################

	@_dbg
	def read_configfile(self,cfg):

		if cfg.has_section('usermap'):

			for (name, value) in cfg.items('usermap'):
					self._addressmap[name] = value

		if cfg.has_section('encryptionmap'):

			for (name, value) in cfg.items('encryptionmap'):
					self._encryptionmap[name] = value.split(":")

		if cfg.has_section('smimeuser'):
			self._smimeuser = dict()
			privatepath=None

			for (name, value) in cfg.items('smimeuser'):
				user=value.split(",")
				cipher=self.parent._SMIMECIPHER

				if len(user)>1:
					tmpcipher=user[1].upper().strip()

					if len(tmpcipher)>0 and tmpcipher!="DEFAULT":
						cipher=tmpcipher

				if len(user)>2:
					upath=os.path.join(self.parent._SMIMEKEYHOME,user[2])
					privatepath=os.path.expanduser(upath)

				upath=os.path.join(self.parent._SMIMEKEYHOME,user[0])
				publicpath=os.path.expanduser(upath)

				if os.path.isfile(publicpath):
					self._smimeuser[name] = [publicpath,cipher,privatepath]

		s=self.parent.smime_factory()
		self._smimeuser.update(s.create_keylist(self.parent._SMIMEKEYHOME))

		for u in self._smimeuser:
			self.debug("SMimeuser: '%s %s'"%(u,self._smimeuser[u]))

		if cfg.has_section('pdf'):

			try:
				self._PDF_PASSWORDFILE=cfg.get('pdf','pdfpasswords')
			except:
				pass

			try:
				self._read_pdfpasswordfile(self._PDF_PASSWORDFILE)
			except:
				self.log("File '%s' could not be opened."
						%self._PDF_PASSWORDFILE)
				self.log_traceback()


	########
	#usermap
	########

	@_dbg
	def usermap(self, user):
		exception=False

		try:
			to_addr=self._addressmap[user]
		except:
			exception=True

		if exception:
			raise KeyError(user)

		self.debug("textbackend usermap %s=>%s"%(user,to_addr))
		return to_addr

	##############
	#encryptionmap
	##############

	@_dbg
	def encryptionmap(self, user):

		try:
			self.debug("get_preferred encryptionmap %s"%user)
			encryption=self._encryptionmap[user]
		except:
			self.debug("No encryption map for user '%s' found"%user)
			raise KeyError(user)

		self.debug("textbackend encryptionmap %s=>%s"%(user,encryption))
		return encryption

	##########
	#smimeuser
	##########

	@_dbg
	def smimeuser(self, user):
		self.debug("textbackend smimeuser check ",user)

		try:
			self.debug("smimeuser %s"%user)
			smime=self._smimeuser[user]
		except:
			self.debug("No smime user '%s' found"%user)
			raise KeyError(user)

		self.debug("textbackend smimeuser %s=>%s"%(user,smime))
		return smime

	#################
	#smimepublic_keys
	#################

	@_dbg
	def smimepublic_keys(self):
		"returns a list of all available keys"
		result=list()

		for user in self._smimeuser:
			result.append(user)

		return result

 	##################
	#smimeprivate_keys
	##################

	@_dbg
	def smimeprivate_keys(self):
		"returns a list of all available private keys"
		result=list()

		for user in self._smimeuser:

			if self._smimeuser[user][2]!=None:
				result.append(user)

		return result

	################
	#set_pdfpassword
	################

	@_dbg
	def set_pdfpassword(self,user,password,autodelete=True):

		if autodelete==True:
			starttime=time.time()
		else:
			starttime=0

		self._pdfpasswords[user]=(password,starttime)

	################
	#get_pdfpassword
	################

	@_dbg
	def get_pdfpassword(self,user):
		pw=None

		try:
			pw=self._pdfpasswords[user]
			return pw[0]
		except:
			pass

		pw= create_password(self.parent._PDFPASSWORDLENGTH)
		self.set_pdfpassword(user,pw)
		return pw

	###################
	#reset_pdfpasswords
	###################

	@_dbg
	def reset_pdfpasswords(self):
		self._pdfpasswords=dict()
		self._read_pdfpasswordfile(self._PDF_PASSWORDFILE)

	#####################
	#del_old_pdfpasswords
	#####################

	@_dbg
	def del_old_pdfpasswords(self,age):
		"age in seconds"
		deluser=[]

		for user in self._pdfpasswords:
			date=self._pdfpasswords[user][1]

			if date>0 and (date + age < time.time()):
				deluser.append(user)

		for user in deluser:
			del self._pdfpasswords[user]
			self.debug("Password for user '%s' deleted"%user)

	########################
	#_read_pdfpasswordfile
	########################

	@_dbg
	def _read_pdfpasswordfile( self,pwfile):

		try:
			f=open(os.path.expanduser(pwfile))
		except:
			self.log("read_pdfpasswordfile: passwords could not be read","e")
			self.log_traceback()
			return

		txt=f.read()
		f.close()
		self._pdfpasswords=dict()

		for l in txt.splitlines():

			try:
				name,passwd=l.split("=",1)
				self._pdfpasswords[name.strip()]=(passwd.strip(),0)
			except:
				pass

#############
#_sql_backend
#############

class _sql_backend(_base_storage):

	#####
	#init
	#####

	@_dbg
	def init(self):
		self._DATABASE="gpgmailencrypt"
		self._USERMAPSQL="SELECT gpguser FROM gpgusermap WHERE user=?"
		self._ENCRYPTIONMAPSQL="SELECT encrypt FROM encryptionmap WHERE user= ?"
		self._SMIMEUSERSQL=("SELECT publickey,cipher FROM smimeusers "
							"WHERE user= ?")
		self._SMIMEPUBLICKEYSQL="SELECT user,publickey,cipher FROM smimeusers"
		self._SMIMEPRIVATEKEYSQL=("SELECT user,privatekey,cipher FROM "
									"smimeusers WHERE privatekey IS NOT NULL")
		self._PDFPASSWORDTABLE="pdfpasswords"
		self._PDFPASSWORDUSERFIELD="user"
		self._PDFPASSWORDPASSWORDFIELD="password"
		self._PDFPASSWORDSTARTTIMEFIELD="starttime"
		self._USER="gpgmailencrypt"
		self._PASSWORD=""
		self._HOST="127.0.0.1"
		self._PORT=4711
		self._USE_SQLUSERMAP=True
		self._USE_SQLENCRYPTIONMAP=True
		self._USE_SQLSMIME=True
		self._USE_SQLPDFPASSWORDS=True
		self._db=None
		self._cursor=None
		self.placeholder="?"
		self._textdelimiter="'"
		self._fielddelimiter="\""
		self._textbackend=get_backend("TEXT",self.parent)
		self._tabledefinition={}
		self._tabledefinition["usermap"]=("create table gpgusermap ("
					"user varchar (255) not null ,gpguser varchar(255));")
		self._tabledefinition["usermapindex"]=("create unique index pindex"
					" on gpgusermap (user);")
		self._tabledefinition["encryptionmap"]=("create table encryptionmap ("
					"user varchar (255) not null ,encrypt varchar(255));")
		self._tabledefinition["encryptionmapindex"]=("create unique index pindex"
					" on encryptionmap (user);")
		self._tabledefinition["pdfpasswords"]=("create table pdfpasswords ("
					"user varchar (255) not null ,"
					"password varchar(255),"
					"starttime float);")
		self._tabledefinition["pdfpasswordsindex"]=("create unique index pindex"
					" on pdfpasswords (user);")
		self._tabledefinition["smimeusers"]=("create table smimeuser("
									"user varchar (255) not null, "
									"privatekey varchar (255), "
									"publickey varchar(255) not null, "
									"cipher varchar (255));")
		self._tabledefinition["smimeusersindex"]=("create unique index pindex"
					" on smimeuser (user);")

	########
	#connect
	########

	def connect(self):
		raise NotImplementedError

	################
	#read_configfile
	################

	@_dbg
	def read_configfile(self,cfg):

		if cfg.has_section('sql'):

			try:
				self._DATABASE=os.path.expanduser(cfg.get('sql','database'))
			except:
				pass

			try:
				self._USERMAPSQL=cfg.get('sql','usermapsql')
			except:
				pass

			try:
				self._ENCRYPTIONMAPSQL=cfg.get('sql','encryptionmapsql')
			except:
				pass

			try:
				self._SMIMEUSERSQL=cfg.get('sql','smimeusersql')
			except:
				pass

			try:
				self._SMIMEPUBLICKEYSQL=cfg.get('sql','smimepublickeysql')
			except:
				pass

			try:
				self._SMIMEPRIVATEKEYSQL=cfg.get('sql','smimeprivatekeysql')
			except:
				pass

			try:
				self._USER=cfg.get('sql','user')
			except:
				pass

			try:
				self._PASSWORD=cfg.get('sql','password')
			except:
				pass

			try:
				self._HOST=cfg.get('sql','host')
			except:
				pass

			try:
				self._PORT=cfg.getint('sql','port')
			except:
				pass

			try:
				self._USE_SQLUSERMAP=cfg.getboolean('sql','use_sqlusermap')
			except:
				pass

			try:
				self._USE_SQLENCRYPTIONMAP=cfg.getboolean('sql',
														'use_sqlencryptionmap')
			except:
				pass

			try:
				self._USE_SQLSMIME=cfg.getboolean('sql',
														'use_sqlsmime')
			except:
				pass

			try:
				self._USE_SQLPDFPASSWORDS=cfg.getboolean('sql',
														'use_sqlpdfpasswords')
			except:
				pass

			try:
				self._PDFPASSWORDUSERFIELD=cfg.get('sql',
													'sqlpdf_userfield')
			except:
				pass

			try:
				self._PDFPASSWORDPASSWORDFIELD=cfg.get('sql',
														'sqlpdf_passwordfield')
			except:
				pass

			try:
				self._PDFPASSWORDSTARTTIMEFIELD=cfg.get('sql',
														'sqlpdf_starttimefield')
			except:
				pass

			try:
				self._PDFPASSWORDTABLE=cfg.get('sql',
												'sqlpdf_passwordtable')
			except:
				pass

		self._textbackend.read_configfile(cfg)
		self.connect()

	########
	#usermap
	########

	@_dbg
	def usermap(self, user):

		if not self._USE_SQLUSERMAP:
			return self._textbackend.usermap(user)

		self.debug(self._USERMAPSQL.replace("?",user))

		if not self.execute(self._USERMAPSQL,user):
			return ""

		r=self._cursor.fetchone()

		try:
			self._cursor.fetchall()
		except:
			pass

		if r==None:
			raise KeyError(user)

		self.debug("sqlbackend %s usermap %s=>%s"%(self._backend,user,r[0]))
		return r[0]

	########
	#execute
	########

	@_dbg
	def execute(self, sql,fields=None):

		self.debug(sql)
		self.connect()

		if self._cursor== None:
			raise KeyError("Database backend not available")

		try:
			f=None

			if fields!=None:
				f=(fields,)

			self._cursor.execute(sql.replace("?",self.placeholder),f)
		except:
			self.log_traceback()
			self._cursor=None
			self._db=None
			return False

		return True

	###############
	#execute_action
	###############

	@_dbg
	def execute_action(self, sql,fields=None,logerror=True):

		self.debug(sql)
		self.connect()

		if self._cursor== None:
			raise KeyError("Database backend not available")

		result=True

		try:
			f=None

			if fields!=None:
				f=(fields,)

			self._cursor.execute(sql.replace("?",self.placeholder),f)
			self._db.commit()
		except:

			if logerror:
				self.log_traceback()

			result=False

		self._cursor=None
		self._db=None
		return result

	##############
	#encryptionmap
	##############

	@_dbg
	def encryptionmap(self, user):

		if not self._USE_SQLENCRYPTIONMAP:
			return self._textbackend.encryptionmap(user)

		if not	self.execute(self._ENCRYPTIONMAPSQL,user):
			return ""

		r=self._cursor.fetchone()

		try:
			self._cursor.fetchall()
		except:
			pass

		if r==None:
			raise KeyError(user)

		self.debug("sqlbackend %s encryptionmap %s=>%s"%(self._backend,
														user,
														r[0]))
		return r[0].split(":")

	#############
	#create_table
	#############

	@_dbg
	def create_table(self,table, logerror=True):
		sql=""

		try:
			sql=self._tabledefinition[table]
		except:
			self.log("SQL definition for table '%s' not found"%table,"e")
			return False

		return self.execute_action(sql,logerror=logerror)

	##################
	#create_all_tables
	##################

	@_dbg
	def create_all_tables(self):
		self.create_table("usermap")
		self.create_table("encryptionmap")
		self.create_table("smimeusers")
		self.create_table("pdfpasswords")
		self.create_table("usermapindex")
		self.create_table("encryptionmapindex")
		self.create_table("smimeusersindex")
		self.create_table("pdfpasswordsindex")

	##########
	#smimeuser
	##########

	@_dbg
	def smimeuser(self, user):

		if not self._USE_SQLSMIME:
			return self._textbackend.smimeuser(user)

		if not 	self.execute(self._SMIMEUSERSQL,user):
			return ""

		r=self._cursor.fetchone()

		try:
			self._cursor.fetchall()
		except:
			pass

		if r==None:
			raise KeyError(user)

		cipher=self.parent._SMIMECIPHER

		if len(user)>1:
			tmpcipher=r[1].upper().strip()

			if len(tmpcipher)>0 and tmpcipher!="DEFAULT":
				cipher=tmpcipher

		upath=os.path.join(self.parent._SMIMEKEYHOME,r[0])
		publicpath=os.path.expanduser(upath)
		result= [publicpath,cipher]
		self.debug("sqlbackend %s smimuser %s=>%s"%(self._backend,
														user,
														result))
		return result

	#################
	#smimepublic_keys
	#################

	@_dbg
	def smimepublic_keys(self):

		if not self._USE_SQLSMIME:
			return self._textbackend.smimepublic_keys()

		rows=list()

		if not 	self.execute(self._SMIMEPUBLICKEYSQL):
			return rows

		for r in self._cursor:

			user=r[0]
			publickey=r[1]
			cipher=self.parent._SMIMECIPHER
			tmpcipher=r[2].upper().strip()

			if len(tmpcipher)>0 and tmpcipher!="DEFAULT":
				cipher=tmpcipher

			result= [user,publickey,cipher]

			if publickey!=None:
				rows.append(result)

		return rows

	##################
	#smimeprivate_keys
	##################

	@_dbg
	def smimeprivate_keys(self):

		if not self._USE_SQLSMIME:
			return self._textbackend.smimepublic_keys()

		rows=list()

		if not	self.execute(self._SMIMEPRIVATEKEYSQL):
			return rows

		for r in self._cursor:

			user=r[0]
			privatekey=r[1]
			cipher=self.parent._SMIMECIPHER
			tmpcipher=r[2].upper().strip()

			if len(tmpcipher)>0 and tmpcipher!="DEFAULT":
				cipher=tmpcipher

			result= [user,privatekey,cipher]

			if privatekey!=None:
				rows.append(result)

		return rows

	################
	#set_pdfpassword
	################

	@_dbg
	def set_pdfpassword(self,user,password,autodelete=True):

		if not self._USE_SQLPDFPASSWORDS:
			return self._textbackend.set_pdfpassword(user,password,autodelete)

		if autodelete==True:
			starttime=time.time()
		else:
			starttime=0

		insertsql=(	"INSERT INTO %(fdlm)s%(table)s%(fdlm)s"
				" (%(fdlm)s%(userfield)s%(fdlm)s,"
				"%(fdlm)s%(passwordfield)s%(fdlm)s, "
				"%(fdlm)s%(starttimefield)s%(fdlm)s) "
				"VALUES (%(tdlm)s%(user)s%(tdlm)s,"
				"%(tdlm)s%(password)s%(tdlm)s,"
				"%(tdlm)s%(starttime)s%(tdlm)s)"
		%{	"passwordfield":self._PDFPASSWORDPASSWORDFIELD,
			"table":self._PDFPASSWORDTABLE,
			"userfield":self._PDFPASSWORDUSERFIELD,
			"starttimefield":self._PDFPASSWORDSTARTTIMEFIELD,
			"starttime":starttime,
			"fdlm":self._fielddelimiter,
			"tdlm":self._textdelimiter,
			"user":user,
			"password":password
		})

		updatesql=(	"UPDATE %(fdlm)s%(table)s%(fdlm)s"
		" SET %(fdlm)s%(passwordfield)s%(fdlm)s = %(tdlm)s%(password)s%(tdlm)s"
		" WHERE %(fdlm)s%(userfield)s%(fdlm)s = %(tdlm)s%(user)s%(tdlm)s"
		%{	"passwordfield":self._PDFPASSWORDPASSWORDFIELD,
			"table":self._PDFPASSWORDTABLE,
			"userfield":self._PDFPASSWORDUSERFIELD,
			"fdlm":self._fielddelimiter,
			"tdlm":self._textdelimiter,
			"user":user,
			"password":password
		})

		if not self.execute_action(insertsql): #,logerror=False):
			self.execute_action(updatesql)

	################
	#get_pdfpassword
	################

	@_dbg
	def get_pdfpassword(self,user):

		if not self._USE_SQLPDFPASSWORDS:
			return self._textbackend.get_pdfpassword(user)

		sql=("SELECT %(fdlm)s%(password)s%(fdlm)s "
				"FROM %(fdlm)s%(table)s%(fdlm)s "
				"WHERE %(fdlm)s%(userfield)s%(fdlm)s =%(tdlm)s%(user)s%(tdlm)s"
		%{	"password":self._PDFPASSWORDPASSWORDFIELD,
			"table":self._PDFPASSWORDTABLE,
			"userfield":self._PDFPASSWORDUSERFIELD,
			"fdlm":self._fielddelimiter,
			"tdlm":self._textdelimiter,
			"user":user})
		self.debug(sql)

		if not 	self.execute(sql):
			return None

		r=self._cursor.fetchone()

		try:
			self._cursor.fetchall()
		except:
			pass

		if r==None:
			pw= create_password(self.parent._PDFPASSWORDLENGTH)
			self.set_pdfpassword(user,pw)
			return pw

		return r[0]

	###################
	#reset_pdfpasswords
	###################

	@_dbg
	def reset_pdfpasswords(self):

		if not self._USE_SQLPDFPASSWORDS:
			return self._textbackend.reset_pdfpasswords()

		sql=("DELETE FROM %(fdlm)s%(table)s%(fdlm)s "
				"WHERE %(fdlm)s%(starttime)s%(fdlm)s >0"
				%	{
					"fdlm":self._fielddelimiter,
					"tdlm":self._textdelimiter,
					"table":self._PDFPASSWORDTABLE,
					"starttime":self._PDFPASSWORDSTARTTIMEFIELD
					})
		self.debug(sql)
		self.execute_action(sql)

	#####################
	#del_old_pdfpasswords
	#####################

	@_dbg
	def del_old_pdfpasswords(self,age):

		if not self._USE_SQLPDFPASSWORDS:
			return self._textbackend.del_old_pdfpasswords(age)

		sql=("DELETE FROM %(fdlm)s%(table)s%(fdlm)s "
				"WHERE %(fdlm)s%(starttime)s%(fdlm)s >0 "
					"AND %(fdlm)s%(starttime)s%(fdlm)s<%(age)s"
				%	{
					"fdlm":self._fielddelimiter,
					"tdlm":self._textdelimiter,
					"table":self._PDFPASSWORDTABLE,
					"starttime":self._PDFPASSWORDSTARTTIMEFIELD,
					"age":(time.time()-age)
					})
		self.debug(sql)
		self.execute_action(sql)

#################
#_SQLITE3_BACKEND
#################

class _SQLITE3_BACKEND(_sql_backend):

	########
	#connect
	########

	def connect(self):
		result=False

		try:
			import sqlite3
		except:
			self.log("SQLITE driver not found","e")
			self.log_traceback()
			return result

		if os.path.exists(self._DATABASE):
			self._db=sqlite3.connect(self._DATABASE)
			self._cursor=self._db.cursor()
			result=True
		else:
			self.log("Database '%s' does not exist"%self._DATABASE,"e")

		return result

###############
#_MYSQL_BACKEND
###############

class _MYSQL_BACKEND(_sql_backend):

	#####
	#init
	#####

	@_dbg
	def init(self):
		_sql_backend.init(self)
		self._PORT=3306
		self.placeholder="%s"
		self._fielddelimiter="`"

	########
	#connect
	########

	def connect(self):
		result=False

		try:
			import mysql.connector as mysql
			from mysql.connector import errorcode
		except:
			self.log("MYSQL (mysql.connector) driver not found","e")
			self.log_traceback()
			return result

		try:
			self._db=mysql.connect(	database=self._DATABASE,
									user=self._USER,
									password=self._PASSWORD,
									host=self._HOST,
									port=self._PORT)
			self._cursor=self._db.cursor()
			result=True
		except mysql.Error as err:

			if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
				self.log(	"Could not connect to database, "
							"wrong username and/or password"
							,"e")
			elif err.errno == errorcode.ER_BAD_DB_ERROR:
				self.log("database %s does not exist"%self._DATABASE,"e")

			self.log_traceback()

		return result

###############
#_ODBC_BACKEND
###############

class _ODBC_BACKEND(_sql_backend):

	#####
	#init
	#####

	@_dbg
	def init(self):
		_sql_backend.init(self)
		self._PORT=0
		self.placeholder="?"

	########
	#connect
	########

	def connect(self):
		result=False

		try:
			import pydodbc as odbc
		except:
			self.log("ODBC (pyodbc) driver not found","e")
			self.log_traceback()
			return result

		try:
			self._db=odbc.connect(database=self._DATABASE)
			self._cursor=self._db.cursor()
			result=True
		except :
			self.log_traceback()

		return result

####################
#_POSTGRESQL_BACKEND
####################

class _POSTGRESQL_BACKEND(_sql_backend):

	#####
	#init
	#####

	@_dbg
	def init(self):
		_sql_backend.init(self)
		self._PORT=5432
		self.placeholder="$1"

	########
	#connect
	########

	def connect(self):
		result=False

		try:
			import psycopg2 as pg
		except:
			self.log("Postqresql(psycopg2) driver not found","e")
			self.log_traceback()
			return result

		try:
			self._db=pg.connect(	database=self._DATABASE,
									user=self._USER,
									password=self._PASSWORD,
									host=self._HOST,
									port=self._PORT)
			self._cursor=self._db.cursor()
			result=True
		except:
			self.log_traceback()

		return result

###############
#_MSSQL_BACKEND
###############

class _MSSQL_BACKEND(_sql_backend):

	#####
	#init
	#####

	@_dbg
	def init(self):
		_sql_backend.init(self)
		self._PORT=1433
		self.placeholder="%s"

	########
	#connect
	########

	def connect(self):
		result=False

		try:
			import pymssql
		except:
			self.log("MS SQL Server(pymssql) driver not found","e")
			self.log_traceback()
			return result

		try:
			self._db=pymssql.connect(	database=self._DATABASE,
									user=self._USER,
									password=self._PASSWORD,
									host=self._HOST,
									port=self._PORT)
			self._cursor=self._db.cursor()
			result=True
		except:
			self.log_traceback()

		return result

################################################################################

################
#get_backendlist
################

def get_backendlist():
	return ["MSSQL","MYSQL","ODBC","POSTGRESQL","SQLITE3","TEXT"]

############
#get_backend
############

def get_backend(backend,parent):
		backend=backend.upper().strip()

		if backend=="SQLITE3":

			try:
				return _SQLITE3_BACKEND(parent=parent,backend="SQLITE3")
			except:
				parent.log("Storage backend %s could not be loaded"%backend,"e")

		elif backend=="MSSQL":

			try:
				return _MSSQL_BACKEND(parent=parent,backend="MSSQL")
			except:
				parent.log("Storage backend %s could not be loaded"%backend,"e")

		elif backend=="MYSQL":

			try:
				return _MYSQL_BACKEND(parent=parent,backend="MYSQL")
			except:
				parent.log("Storage backend %s could not be loaded"%backend,"e")

		elif backend=="ODBC":

			try:
				return _ODBC_BACKEND(parent=parent,backend="ODBC")
			except:
				parent.log("Storage backend %s could not be loaded"%backend,"e")

		elif backend=="POSTGRESQL":

			try:
				return _POSTGRESQL_BACKEND(parent=parent,backend="POSTGRESQL")
			except:
				parent.log("Storage backend %s could not be loaded"%backend,"e")

		# default backend=="TEXT":
		return _TEXT_BACKEND(parent=parent,backend="TEXT")

