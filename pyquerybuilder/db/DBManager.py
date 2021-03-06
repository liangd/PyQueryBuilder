#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
DBManager module 
"""
__revision__ = "$Id: $"
__version__ = "$Revision: $"
__author__ = "Valentin Kuznetsov"

# system modules
import sys  
import time
import types
import traceback

# SQLAlchemy modules
import sqlalchemy

# local modules
from pyquerybuilder.qb.DotGraph import DotGraph
from pyquerybuilder.utils.Errors import Error

def print_list(input_list, msg = None):
    """Print input list"""
    if  msg:
        s_msg = "-" * len(msg)
        print msg
        print s_msg
    for item in input_list:
        print item

def print_table(t_list, o_list, l_list, msg = None):
    """Distribute discription of this table to diff method"""
    if  msg:
        print msg
    print t_list
    for idx in xrange(0, len(o_list)):
        print o_list[idx]
    
class DBManager(object):
    """
    A main class which allows access to underlying RDMS system.
    It is based on SQLAlchemy framework, see
    http://www.sqlalchemy.org
    """
    def __init__(self, verbose = 0):
        """
        Constructor. 
        """
        self.verbose     = verbose
        self.members     = ['engine', 'db_tables', 'table_names', 
                            'db_type', 'db_owner', 'db_schema', 
                            'meta_dict', 'drivers', 'aliases']
        # all parameters below are defined at run time
        self.t_cache     = []
        self.engine      = {}
        self.db_tables   = {}
        self.table_names = {}
        self.db_type     = {}
        self.db_owner    = {}
        self.db_schema   = {}
        self.meta_dict   = {}
        self.drivers     = {}
        self.aliases     = {}
        self.con         = None
        
    def write_graph(self, db_alias, f_mat=None):
        """
        Write graph of DB schema to db_alias.dot file
        Using dot in shell to create result in given format
        """
        file_name = "%s.dot" % db_alias
        if  self.verbose:
            print "Writing graph of DB schema to", file_name
        dot = DotGraph(file(file_name, "w"))
        # load all tables before building a graph
        t_dict = self.load_tables(db_alias) 
        if  self.verbose:
            print t_dict
        for key in t_dict.keys():
            table = t_dict[key]
            table_name = key
            f_keys = table.foreign_keys
            for f_key in f_keys:
                right = f_key.column.table.name
                if right != 'person': # exclude person table
                    dot.add_edge(table_name, right)
        dot.finish_output()
  
    def dbname(self, arg):
        """
        Generate dbname as corresponding db_type in arg
        """
        if self.drivers.has_key(arg):
            arg = self.drivers[arg]
        db_type, db_name, _, _, host, _, owner, file_name = \
                             self.parse(arg)
        if db_type.lower() == 'oracle': 
            name = db_name
            if owner: 
                name += "-%s" % owner
            return "%s-%s |\#> " % (db_type, name)
        if db_type.lower() == 'mysql': 
            return "%s-%s-%s |\#> " % (db_type, db_name, host)
        if db_type.lower() == 'postgresql':
            return "%s-%s-%s |\#> " % (db_type, db_name, host)
        if db_type.lower() == 'sqlite': 
            f_name = file_name.split("/")[-1]
            return "%s-%s |\#> " % (db_type, f_name)
        return "%s-%s |\#> " % (db_type, db_name)
  
    def show_table(self, db_alias):
        """
        Print out list of tables in DB
        """
        if  self.table_names.has_key(db_alias):
            tables = self.table_names[db_alias]
            tables.sort()
            if  self.verbose:
                print_list(tables, "\nFound tables:")
        else:
            if  self.verbose:
                print_list([]," \nFound tables")
        
    def desc(self, db_alias, table):
        """
        Describe a table from DB 
        """
        tables = self.load_tables(db_alias, table) # load table from DB
        if  self.verbose:
            print tables
        tab_obj = tables[table]
        if  self.verbose:
            print "table object:", tab_obj
        t_list = ['Name', 'Type', 'Key', 'Default',
                  'Autoincrement', 'Foreign Keys']
        o_list = [] # contains tuple of values for t_list
        l_list = [len(x) for x in t_list] # column width list
        for col in tab_obj.columns:
            key   = ""
            if col.unique: 
                key = "unique"
            elif col.primary_key: 
                key = "primary"
            value = "NULL"
            if col.default: 
                value = col.default
            f_keys = ""
            for f_key in col.foreign_keys:
                f_keys += "%s " % f_key.column
            v_list = (col.name, col.type, key, value, col.autoincrement, f_keys)
            o_list.append(v_list)
            for idx in xrange(0, len(v_list)):
                if l_list[idx] < len(str(v_list[idx])): 
                    l_list[idx] = len(str(v_list[idx]))
        o_list.sort() 
        if  self.verbose:
            print_table(t_list, o_list, l_list)
        return len(o_list)
  
    def dump(self, db_alias, file_name = None):
        """
        Try to create a table and dump results in provided file
        """
        tables = self.load_tables(db_alias) 
        # load all tables from DB in order to dump DDL
#        db_type = self.db_type[db_alias]
#        msg    = "--\n-- Dump %s.\n-- %s\n" % \
#              (db_alias, makeTIME(time.time()))
        msg = "--\n-- Dump %s.\n-- %s\n" % (db_alias, time.time())
        if  file_name:
            l_file = open(file_name, 'w') 
            l_file.write(msg)
        else:
            if  self.verbose:
                print msg
        for t_name in tables.keys():
            table = tables[t_name]
            try:
                table.create()
            except :
                error = sys.exc_info()[1]
                if  file_name:
                    l_file.write("%s;\n" % error.statement)
                else:
                    if  self.verbose:
                        print "%s;\n" % error.statement
            try:
                result = self.con.execute("SELECT * FROM %s" % t_name)
                for item in result:
                    if type(item) is types.StringType:
                        raise Exception, item + "\n"
                    columns = str(item.keys()).replace("[", \
                                        "(").replace("]", ")")
                    values  = str(item.values()).replace("[", \
                                       "(").replace("]", ")")
                    stm = "INSERT INTO %s %s VALUES %s;" % \
                             (t_name, columns, values)
                    if  file_name:
                        l_file.write(stm + "\n")
                    else:
                        if  self.verbose:
                            print stm
            except :
                raise traceback.print_exc()
        if file_name:
            l_file.close()
  
    def migrate(self, db_alias, arg):
        """
        Migrate schema from db_alias to self.aliases[arg]
        have to follow the contraints sequence in oracle
        """
        tables = self.load_tables(db_alias) # load all tables from DB
        db_con = self.con
        self.connect(arg)
        new_dbalias = self.aliases[arg]
        remote_engine = self.engine[new_dbalias]
        meta = sqlalchemy.MetaData()
        meta.bind = remote_engine
        table_names = tables.keys()
        table_names.sort()
        con = remote_engine.connect()
        for table in table_names:
            if  self.verbose:
                print table
            new_table = tables[table].tometadata(meta)
#            tables[table].create(bind = remote_engine, checkfirst=True)
            new_table.create(bind = remote_engine, checkfirst=True)
            query = "select * from %s" % table
            try:
                result = db_con.execute(query)
            except Error:
                raise traceback.print_exc()
            for item in result:
                if type(item) is types.StringType:
                    raise item + "\n"
                ins = new_table.insert(values = item.values())

                try:
                    con.execute(ins)
                except Error:
                    raise traceback.print_exc()
        con.close()
        if  self.verbose:
            print "The content of '%s' has been successfully migrated to '%s'" % \
                          (db_alias, new_dbalias)
        self.close(new_dbalias)
  
    def create_alias(self, name, params):
        """Update self.aliases"""
        self.aliases[name] = params
  
    def execute(self, query, list_results = 1):
        """Execute query and print result"""
        self.t_cache = []
        try:
            result = self.con.execute(query)
        except Error:
            raise Exception
        if not list_results: 
            return None
#        return self.print_result(result, query)
#        self.print_result(result, query)
        return result
  
    def print_result(self, result, query):
        """
        Print result and query
        return query and title list and values list
        """
        o_list  = []
        t_list  = []
        l_list  = []
        for item in result:
            if type(item) is types.StringType:
                raise Exception, item+"\n"
            if not (type(result) is types.ListType):
                self.t_cache.append(item)
            if not t_list:
                t_list = list(item.keys())
                l_list = [len(x) for x in t_list]
            v_list = item.values()
            o_list.append(v_list)
            for idx in xrange(0, len(v_list)):
                if l_list[idx] < len(str(v_list[idx])): 
                    l_list[idx] = len(str(v_list[idx]))
        if  self.verbose:
            print_table(t_list, o_list, l_list, query)
        return (query, t_list, o_list)
  
    def drop_db(self, db_alias):
        """
        Drop database
        """
        tables = self.load_tables(db_alias)
        for t_name in tables.keys():
            table = tables[t_name]
            try:
                table.drop()
            except Error:
                traceback.print_exc()
        self.db_tables.pop(db_alias)
  
    def drop_table(self, db_alias, table_name):
        """
        Drop table from provided database
        """
        tables = self.load_tables(db_alias, table_name)
        if  tables.has_key(table_name):
            tab_obj = tables[table_name]
            try:
                tab_obj.drop()
            except :
                traceback.print_exc()
            try:
                tables.pop(table_name)
            except :
                pass
            try:
#                print self.db_tables
                self.db_tables[db_alias].pop(table_name)
            except :
                pass
            try:
                self.table_names[db_alias].remove(table_name)
            except :
                traceback.print_exc()

    def reconnect(self, db_alias, reload_tables = None):
        """
        Close existing connection and reconnect to database
        """
        self.con.close()
        self.con = self.engine[db_alias].connect()
        if reload_tables:
            self.db_tables = {}
            self.table_names = {}
        self.load_table_names(db_alias)
  
    def close(self, db_alias):
        """
        Close connection to database
        """
        self.con.close()

        for dict in self.members:
            member = getattr(self, dict)
            if  member.has_key(db_alias):
                try:
                    member.pop(db_alias)
                except Error:
                    pass
        if self.verbose:
            print "database connection %s has been closed" % \
                 db_alias
        
    def parse(self, arg):
        """ 
        Parse provided input to make data base connection.
        SQLAlchemy support the following format :

        .. doctest::

            driver://username:password@host:port/database,

        while here we extend it to the following structure 
        (suitable for ORACLE):

        .. doctest::

            driver://username:password@host:port/database:db_owner
        """
        port      = None
        host      = None
        owner     = None
        file_name = None
        db_name   = None
        db_user   = None
        db_pass   = None
        try:
            driver, dbparams = arg.split("://")
        except Error:
            msg = "Fail to parse connect argument '%s'\n" % arg
            raise Exception, msg + "\n"
        if  dbparams.find("@") != -1:
            user_pass, rest  = dbparams.split("@")
            db_user, db_pass = user_pass.split(":")
            if  rest.find("/") != -1:
                host_port, dbrest = rest.split("/")
                try:
                    host, port = host_port.split(":") 
                except Error:
                    host = host_port
            else:
                dbrest = rest
            try:
                db_name, owner  = dbrest.split(":")
            except :
                db_name = dbrest
        else: # in case of SQLite, dbparams is a file name
            file_name = dbparams
            db_name   = file_name.split("/")[-1]
            if  driver != 'sqlite':
                msg = "'%s' parameter is not supported for driver '%s'" % \
                          (file_name, driver)
                raise Exception, msg + "\n"
        return (driver.lower(), db_name, db_user, db_pass, 
                             host, port, owner, file_name)
  
    def connect(self, driver):
        """Connect to DB"""
        if self.drivers.has_key(driver):
            arg = self.drivers[driver]
        else:
            arg = driver
        db_type, db_name, db_user, db_pass, host, port, db_owner, file_name = \
            self.parse(arg)
        db_schema = None
        if db_type =='oracle' and db_owner:
            db_alias  = '%s-%s' % (db_name, db_owner)
            db_schema = db_owner.lower()
        else:
            db_alias = db_name
            if db_type: 
                db_alias += "-" + db_type
#            print "db_alias: %s"% db_alias
        if  not self.drivers.has_key(driver):
            self.drivers[db_alias] = driver
            self.aliases[driver] = db_alias

        e_type  = str.lower(db_type)
        if  self.verbose:
            print "Connecting to %s (%s back-end), please wait ..." % \
                     (db_alias, db_type)
  
        # Initialize SQLAlchemy engines
        if  not self.engine.has_key(db_alias):
            e_name = ""
            if e_type == 'sqlite':
                e_name = "%s:///%s" % (e_type, file_name)
                engine = sqlalchemy.create_engine(e_name)
            elif e_type == 'oracle':
                e_name = "%s://%s:%s@%s" % (e_type, db_user, db_pass, db_name)
                engine = sqlalchemy.create_engine(e_name, 
                            strategy = 'threadlocal', threaded = True)
            elif e_type == 'mysql':
                e_name = "%s://%s:%s@%s/%s" % (e_type, db_user, 
                                          db_pass, host, db_name)
                engine = sqlalchemy.create_engine(e_name, 
                                 strategy = 'threadlocal')
            elif e_type == 'postgresql':
                e_name = "%s://%s:%s@%s/%s" % (e_type, db_user,
                                           db_pass, host, db_name)
                engine = sqlalchemy.create_engine(e_name,
                                 strategy = 'threadlocal')
            else:
                # printExcept("Unsupported DB engine back-end")
                print Exception, "Unsupported DB engine back-end"
            self.engine[db_alias] = engine
        self.con = self.engine[db_alias].connect()
        if  not self.db_type.has_key(db_alias): 
            self.db_type[db_alias] = e_type
        if  not self.db_owner.has_key(db_alias) : 
            self.db_owner[db_alias] = db_owner
        if  not self.db_schema.has_key(db_alias): 
            self.db_schema[db_alias] = db_schema
        if  not self.meta_dict.has_key(db_alias):
            db_meta = sqlalchemy.MetaData()
            db_meta.bind = self.engine[db_alias]
            self.meta_dict[db_alias] = db_meta
        if  not self.table_names.has_key(db_alias): 
            self.table_names[db_alias] = self.load_table_names(db_alias)
        return self.con
  
    def load_table_names(self, db_alias):
        """
        Retrieve table names for provided database name.
        """
        e_type = self.db_type[db_alias]
        engine = self.engine[db_alias]
        if  e_type == 'oracle' and self.db_owner[db_alias]:
            query = "SELECT table_name FROM all_tables WHERE owner='%s'" % \
                     self.db_owner[db_alias].upper()
            result = self.con.execute(query)
            table_names = [x[0].lower().split(".")[-1] for x in result]
            query = "SELECT view_name FROM all_views WHERE owner='%s'" % \
                    self.db_owner[db_alias].upper()
            result = self.con.execute(query)
            table_names += [x[0].lower().split(".")[-1] for x in result]
        else:
            table_names = engine.table_names()
        return table_names
  
    def load_tables(self, db_alias, table_name = None):
        """
        Load table objects for provided database. The optional table_name
        parameter allows to load concrete table from the database
        """
        if  self.db_tables.has_key(db_alias):
            tables = self.db_tables[db_alias]
        else:
            tables = {}
        db_meta = self.meta_dict[db_alias]
        e_type = self.db_type[db_alias]
        kwargs = {}
        kwargs = {'autoload':True}
        for t_name in self.table_names[db_alias]:
            tab_name = t_name.lower()
            if  tables.has_key(tab_name): 
                continue
            if  table_name and tab_name != table_name: 
                continue
            if  e_type == 'oracle':
                kwargs['useexisting'] = True
            tables[tab_name] = sqlalchemy.Table(tab_name, db_meta, **kwargs)
        self.db_tables[db_alias] = tables
        return tables
  
