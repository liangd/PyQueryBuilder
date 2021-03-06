"""TestDBManger"""
import unittest
from pyquerybuilder.db.DBManager import DBManager

class TestDBManager(unittest.TestCase):
    """test DBManager"""
    def setUp(self):
        """default"""
        self.manager = DBManager()
        self.url = '__URL__'
        self.murl = '__MURL__'
        self.pname = '__PNAME__'
        self.name = '__NAME__'
        self.mname = '__MNAME__'

    def test_get_dbname(self):
        """test execute query on sqlite DB"""
        db_name = self.manager.dbname(self.url)
#        print "db_name: %s" % db_name
        self.assertEqual(db_name, self.pname)

    def test_connection(self):
        """test get connection with diff DB"""
        self.manager.connect(self.url)
        self.manager.show_table(self.name)
        results = self.manager.execute("select count(*) from t1")
        rows = results.fetchall()
        self.manager.close(self.name)
        self.assertEqual(3, rows[0][0])
        rows = []

    def test_desc(self):
        """test describe database"""

        self.manager.connect(self.url)
        length = self.manager.desc(self.name, 't1')
        self.assertEqual(4, length)
        length = self.manager.desc(self.name, 't2')
        self.assertEqual(4, length)
        self.manager.close(self.name)

    def test_dump(self):
        """test dump database in file"""

        self.manager.connect(self.url)
        self.manager.dump(self.name)
        self.manager.close(self.name)

    def test_migrate_drop(self):
        """test migrate database"""

        self.manager.connect(self.url)
        self.manager.migrate(self.name, \
               self.murl)
        self.manager.close(self.name)
        self.manager.connect(self.murl)

        results = self.manager.execute("select count(*) from t1")
        rows = results.fetchall()
        self.assertEqual(3, rows[0][0])
        self.manager.close(self.mname)
        
        self.manager.connect(self.murl)
        self.manager.drop_table(self.mname, 't2')
        self.manager.drop_db(self.mname)
        self.manager.close(self.mname)

    def test_reconnect(self):
        """test reconnect to database"""

        self.manager.connect(self.url)
        self.manager.reconnect(self.name)
        self.manager.close(self.name)

def suite():
    """suite of unittest"""
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestDBManager))
    return suite

#
# main
#
if __name__ == "__main__":

    unittest.TextTestRunner(verbosity=2).run(suite())

