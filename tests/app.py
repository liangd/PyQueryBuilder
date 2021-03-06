#!/usr/bin/env python
"""
App for testing QueryBuilder 
"""


import traceback
from collections import deque
from logging import getLogger

from sqlalchemy import select, MetaData
#from sqlalchemy.sql import and_, or_, not_
from sqlalchemy.sql.expression import func

from pyquerybuilder.qb.Schema import Schema, find_table
from pyquerybuilder.db.DBManager import DBManager, print_list
from pyquerybuilder.utils.Errors import Error
from pyquerybuilder.tools.Mapper import Mapper
from pyquerybuilder.parser import qparse
#from pyquerybuilder.qb.ConstructQuery import ConstructQuery

from UnittestDB import load_from_file

_LOGGER = getLogger("ConstructQuery")

def get_table_column(metadata, keyword):
    """get table or column object from schema"""
    if keyword.count('.'):
        (entity, attr) = keyword.split('.')
        table = find_table(metadata, entity)
        if table:
            return table.columns[attr]
        else: 
            raise Error("ERROR can't find table %s" % str(entity))
    else:
        entity = keyword
        table = find_table(metadata, entity)
        if table:
            return table
        else: 
            raise Error("ERROR can't find table %s" % str(entity))


def generate_query(metadata, query):
    """generate query from parse result"""
    if query:
        key_list = []
        for keyword in query['keywords']:
            if len (keyword) == 1:
                key_list.append(get_table_column(metadata, keyword[0]))
            elif keyword[1] in ('count', 'max', 'min', 'sum'):
                key_list.append( \
        getattr(func, keyword[1])(get_table_column(metadata, keyword[0])))
            else:
                raise Error(\
                "ERROR: invalid keyword format %s" % str(keyword))

        whereclause = None
        stack = []
        queue = deque([])
        constraint = None
        if query.has_key('constraints'):
            stack.append(query['constraints'])
            constraint = stack.pop()
        else:
            return  select(key_list, whereclause)
        # sort out the sequence by using a stack a queue        
        while constraint:
            if type(constraint) is type([]):
                if len(constraint) == 1:
                    # operate miss
                    constraint = constraint[0]
                    stack.append(constraint)
                else:
                    multiple = False
                    for index in range(0, len(constraint)):
                        cons = constraint[index]
                        if type(cons) is type('str'):
                            if multiple == True:
                                stack.pop()
                            stack.append(cons)
                            stack.append(constraint[index-1])
                            stack.append(constraint[index+1])
                            multiple = True
            elif type(constraint) is type({}):
                queue.append(constraint)
            elif type(constraint) is type('str'):
                queue.append(constraint)
            if len(stack) == 0:
                break
            constraint = stack.pop()
        # Now we have correct sequence in queue
#        print queue
        constraint = queue.popleft()
        if len(queue) == 0:
            column = get_table_column(metadata, constraint['keyword'][0])
            whereclause = column.op(constraint['sign'])(constraint['value'])
            return  select(key_list, whereclause)
        # right use as right hand to hold constraint
        right = None
        # left use as left hand to hold constraint
        left = None
        # extra use as A B C or and in queue
        extra = None
        while constraint:
            if type(constraint) is type({}):
                if right is None :
                    right = constraint
                elif left is None:
                    left = constraint
                elif extra is None:
                    extra = right
                    right = left
                    left = constraint
                else:
                    raise Error("ERROR: consecutive constraint >3 in queue")
            elif type(constraint) is type('str'):
                if right and left :
                    # construct whereclause
                    if type(right) == type({}):
                        column = get_table_column(metadata, right['keyword'][0])
                        right = column.op(right['sign'])(right['value'])
                    if type(left) == type({}):
                        column =  get_table_column(metadata, left['keyword'][0])
                        left = column.op(left['sign'])(left['value'])
                    if constraint == 'and':
                        whereclause = (left & right)
                    elif constraint == 'or':
                        whereclause = (left | right)
                    left = None
                    right = whereclause
                    if extra:
                        left = right
                        right = extra 
                        extra = None
            if len(queue) == 0:
                break
            constraint = queue.popleft() 
#                print whereclause
#        print "type whereclause is ", type(whereclause)
        return  select(key_list, whereclause)                            



def test_query_parser(mapper, in_put):
    """input query ==parse==> output dictionary 
       ==mapper==> select sentences"""
    presult = qparse.parse(in_put)
    if presult == None:
        raise Error("parse result is empty")
#    print "parse result: ", presult 
    # construct a query 
    keywords =  presult['keywords']
    for keyword in keywords:
        if mapper.has_key(keyword[0]):
            key = mapper.get_column(keyword[0])
#            print "%s ==map==> %s"% (keyword[0], key)
            keyword.remove(keyword[0])
            keyword.insert(0, key)

        else:
            _LOGGER.error("""keyword not in mapper %s""", 
                       str(keyword[0]))
            raise Error(\
              "ERROR: keyword not in mapper %s" % str(keyword[0]))
            
    constraint = None
    if presult.has_key('constraints'):
        constraint = presult['constraints']
    stack = []
    while (constraint):
        # push all constraint on [] into stack
        if type(constraint) is type([]):
            for con in constraint:
                stack.append(con)

        cons = stack.pop()
        # we find a constraint do mapper
        if type(cons) is type({}):
            keyword = cons['keyword']
            if mapper.has_key(keyword[0]):
                key = mapper.get_column(keyword[0])
                cons['keyword'] = [key]
#                print "%s ==map==> %s"% (keyword[0], key)
            else: 
                _LOGGER.error("""keyword not in mapper %s""",
                       str(keyword[0]))
                raise Error("ERROR: keyword not in mapper %s"\
                         % str(keyword[0]))
            # we finished the last element in stack
            if len(stack) == 0:
                break
            constraint = stack.pop()
        # we find a [] put it in constraint
        elif type(cons) is type([]):
            constraint = cons

    _LOGGER.debug("""user input is: %s""" % str(in_put))
    _LOGGER.debug("""parse result is: %s""" % str(presult))
#    print presult
    return presult

class App():
    """Application demo"""
    def __init__(self, verbose = 0):
        """initialize"""
        class MySchema(object):
            """class encapsulate tables structure"""
            def __init__(self, tables=None):
                """initialize """
                self.tables = tables

            def set_tables(self, tables):
                """set tables"""
                self.tables = tables
        self.schema = MySchema()
        self.manager = None
        self.db_name = None
        self.querybuilder = None
        self.url = None
        self.mapper = None

    def set_manager(self, url, alias):
        """set manager"""
        self.manager = DBManager()
        self.url = url
        self.db_name = alias
        
    def get_db_connection(self):
        """get db connection"""
        return self.manager.connect(self.url)    

    def close_db_connection(self):
        """close db connection"""
        return self.manager.close(self.db_name)
    
    def set_mapper(self, mapfile='map.yaml'):
        """set mapper"""
        self.mapper = Mapper()
        self.mapper.load_mapfile(mapfile)

    def set_querybuilder(self, schema_file=None):
        """set querybuilder"""
        metadata = MetaData()
        tables = None
        if schema_file:
            metadata = load_from_file(schema_file)
            tables = metadata.tables
            self.schema = metadata
        else: 
            tables = self.manager.load_tables(self.db_name)
            self.schema.set_tables(tables)
        self.querybuilder = Schema(tables)
           
    def parse_input(self, in_puts):
        """parse input"""
        return test_query_parser(self.mapper, in_puts)
    
    def generate_sqlalchemy_query(self, query):
        """generate sqlalcemy query"""
#    print type(process_dataset.c.Name)
#    print type(process_dataset.columns['Name'])
        return generate_query(self.schema, query)
    
    def build_query(self, query):
        """build query"""
#    print "query._raw_columns is ", select_test._raw_columns
#    print "query.inner_columns is ", [col for col in select_test.inner_columns]
#    print "query.froms is ", select_test.froms
#    print dir(select_test)
        return  self.querybuilder.build_query(query)

    def execute_query(self, query):
        """execute query"""
        try:
            result =  self.manager.execute(query)
            return result
        except Error:
            print Error
            return None

if __name__ == '__main__':
    INPUTS = """find dataset, file, file.block  where dataset 
               like names and primds.startdate > 20100501 or 
                block.size < 250"""
    INPUTS = """find block, file where (dataset like names and 
               primds.startdate > 20100501) or block.size < 250"""
    INPUTS = """find dataset, count(file), max(block.size) 
               where dataset like cosmic and (dataset.createdate>2010 
               or (block.size > 200 and file.createdate > 
               2010-01-01 02:30:30 CST) or block.size < 500)"""
    INPUTS = """find  file where dataset.createdate > 0 
               or (block.size > 0 and file.createdate > 0) 
               or block.size < 0"""
    APP = App()
    MURL = 'oracle://liangd:tiger@localhost.localdomain:1522/orcl:liangd'
    DB_ALIAS = 'orcl-liangd'
    APP.set_manager(MURL, DB_ALIAS)
    APP.get_db_connection()
    APP.set_querybuilder()
    APP.set_mapper('testmap.yaml')
#    query = APP.parse_input(input)
#    query = APP.generate_sqlalchemy_query(query)
#    result = APP.execute(query)
#    print_list(result)
    
#    test_single_query(manager,result)
    while True:
        try:
            INPUTS = raw_input('calc > ')
        except EOFError:
            break
        if not INPUTS:
            continue
        try:
            MQUERY = APP.parse_input(INPUTS)
            print MQUERY
            MQUERY = APP.generate_sqlalchemy_query(MQUERY)
            print MQUERY
            MQUERY = APP.build_query(MQUERY)
            print MQUERY
            RESULT = APP.execute_query(MQUERY)
            if RESULT: 
                print_list(RESULT)
        except Error:
            traceback.print_exc()
            continue
        

    APP.close_db_connection()

