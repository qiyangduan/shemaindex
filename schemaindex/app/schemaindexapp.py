from config import cfg
import os
import time
import logging
import simplejson as json
import sys
import dbmodels
# from util import SQLAlchemyReflectEngine
from sqlalchemy import Column, DateTime, String, Integer, func


from whoosh import index
from whoosh.qparser import QueryParser



class SchemaIndexApp:
    """ The runtime platform for running all mining models
    """

    MODEL_DATAFRAME_DIR = 'data'
    MODEL_INSTANCE_DIR = 'instance'
    MODEL_SPEC_DIR = 'spec' # Save the specs of a specific model, including file mining_model.json
    MODEL_SPEC_PATH = 'spec' # Save all model_spec programs. One spec may serve multiple models
    MODEL_SPEC_FILENAME = 'mining_model.json'
    TIME_FORMATER = "%Y-%m-%d %H:%M:%S"

    db_session = dbmodels.create_session(bind=dbmodels.engine)
    logger = logging.getLogger('stanmo_logger')
    def __init__(self):
        self.stanmo_home = cfg['main']['schemaflex_home']
        # Add the plugin (model specs) home to sys path for dynamic loading all model specs defined under $STANMO_HOME/spec
        sys.path.append(os.path.join(self.stanmo_home, self.MODEL_SPEC_PATH))
        self.schemaindex_init()

        self.logger.debug('stanmo platform is started.') # will not print anything

    def schemaindex_init(self):
        # import os.path
        to_init_indicator =   cfg['main']['init_indicator_file']


        if not os.path.exists(to_init_indicator):
            return;
        os.remove(to_init_indicator)
        # os.remove(textidx)

        db_file_path = os.path.join(os.getcwd(), cfg['database']['sqlite_file'])
        if os.path.exists(db_file_path):
            os.remove(db_file_path)
            # if(False):
        try:
            engine = dbmodels.create_engine('sqlite:///' + db_file_path)
            print('creating ... ' + db_file_path)
            dbmodels.Base.metadata.create_all(engine)
            self.scan_reflect_plugins()
            print("schemaindex: Initialized before the first request. db file is: " + db_file_path)
        except Exception as e:
            print(str(e))

    def delete_data_soruce(self,ds_dict = None):
        session = dbmodels.create_session(bind=dbmodels.engine)
        session._model_changes={}

        tab_result = session.query(dbmodels.MTable).filter_by(ds_name=ds_dict['ds_name'])
        if tab_result.count() > 0 and (not ds_dict['delete_reflected_database_automatic'] == 'on'):
            return {'message_type': 'danger',
                    'message_title': 'Error',
                    'message_body':'the data source "' + ds_dict['ds_name'] + '" contains metadata. Please check " Delete Contents in Data Source" and try again'}

        session.begin()
        session.query(dbmodels.MDatabase).filter_by(ds_name=ds_dict['ds_name']).delete(synchronize_session=False)
        session.commit()
        return {'message_type': 'info',
                'message_title': 'Info',
                'message_body': 'the data source "' + ds_dict['ds_name'] + '" is deleted.'}

    def add_data_soruce(self,ds_dict = None):
        session = dbmodels.create_session(bind=dbmodels.engine)
        session._model_changes={}

        session.begin()
        session.add_all([
            dbmodels.MDatabase(display_name=ds_dict['display_name'] ,
                               ds_name=ds_dict['ds_name'] ,
                               nbr_of_tables=0,
                               nbr_of_columns=9,
                               db_desc = 'list of db',
                               db_comment = 'customer rating for each product',
                               created_date = func.now(),
                               db_url= ds_dict['db_url']
                    )
        ])
        session.commit()
        dbrs1 = session.query(dbmodels.MDatabase).filter_by(ds_name=ds_dict['ds_name'])
        db = dbrs1.first()
        if db is None:
            print('error: did not find database')
        return db

    def update_data_soruce(self,ds_dict = None):
        session = dbmodels.create_session(bind=dbmodels.engine)
        session._model_changes={}

        session.begin()
        # db1 = dbmodels.MDatabase.query.filter_by(ds_name=ds_dict['ds_name']).first()
        session.query(dbmodels.MDatabase).filter_by(ds_name=ds_dict['ds_name']).\
            update({'display_name': ds_dict['display_name'],
                    'db_type': ds_dict['db_type'],
                    'db_url': ds_dict['db_url'],
                    'db_desc':'list of dbupdated'})

        #db1.db_desc = 'list of db updated'
        #db1.db_url = ds_dict['db_url']
        session.commit()
        dbrs1 = session.query(dbmodels.MDatabase).filter_by(ds_name=ds_dict['ds_name'])
        db = dbrs1.first()
        if db is None:
            print('error: did not find database')
        return db



    def get_data_source_name_list(self):

        rs = self.db_session.query(dbmodels.MDatabase) #.filter_by(name='ed')

        ds_list = []
        for row in rs:
            ds_list.append({'name': row.ds_name , 'url': row.db_url } )
        return  ds_list

    def global_whoosh_search(self, q = ''):

        indexdir = cfg['main']['schemaflex_text_index_path']
        rs = self.db_session.query(dbmodels.MDatabase) #.filter_by(name='ed')
        ix = index.open_dir(indexdir)
        res = []
        with ix.searcher() as searcher:
            query = QueryParser("table_info", ix.schema).parse(q)
            results = searcher.search(query)
            '''
            print(results[0])
            b = simplejson.loads(results[0]['table_info'])
            print(b)
            print(results.__len__())
            '''
            for r in results:
                res.append(json.loads(r['table_info']))

        return res
    def get_whoosh_search_suggestion(self, q = ''):

        indexdir = cfg['main']['schemaflex_text_index_path']
        rs = self.db_session.query(dbmodels.MDatabase) #.filter_by(name='ed')
        ix = index.open_dir(indexdir)
        res = []
        with ix.reader() as r:
            # print (r.most_frequent_terms("table_info", number=5, prefix='dep'))
            for aterm in r.most_frequent_terms("table_info", number=5, prefix=q):
                res.append(aterm[1]) # The result was like (1.0, 'dept_manager'), but here i need only a keyword
                print (aterm)

        return res

    def get_data_source_rs(self):

        rs = self.db_session.query(dbmodels.MDatabase).order_by(dbmodels.MDatabase.ds_name.asc()) #.filter_by(name='ed')
        return  rs

    def get_plugin_name_list(self):
        plugins = []
        rs =  self.db_session.query(dbmodels.MPlugin)
        for p in rs:
            plugins.append(p.plugin_name)
        return  plugins


    def get_table_list_for_data_source_rs(self, param_ds_name = ''):
        sql = '''
                SELECT c.ds_name,  c.table_name, t.table_comment, group_concat(c.column_name)   as column_names
                FROM mcolumn c, mtable t
                where c.table_name = t.table_name and c.ds_name = t.ds_name and t.ds_name = \'''' + param_ds_name + '''\'
                GROUP BY c.ds_name, c.table_name;
                '''

        tabrs = dbmodels.engine.execute(sql)
        return  tabrs


    def reflect_db(self,data_source_name=None):
        session = dbmodels.create_session(bind=dbmodels.engine)
        dbrs = session.query(dbmodels.MDatabase).filter_by(ds_name=data_source_name)
        for row in dbrs:
            adb = SQLAlchemyReflectEngine()
            adb.reflect_database(display_name=row.display_name,
                                 ds_name=row.ds_name,
                                 db_type=row.db_type,
                                 db_url=row.db_url
                                 )
    def list_data_sources(self):
        model_list = []
        models = []

        session = dbmodels.create_session(bind=dbmodels.engine)
        dbrs = session.query(dbmodels.MDatabase)  # .filter_by(name='ed')


        for db in dbrs:
                models.append(db)
        if len(models) > 0:
            print('{0:20}   {1:20}  {2:35}  '.format('data source name',
                                                                           'data source type',
                                                                           'URL'
                                                                           ))
            for a_model in models:
                print('{0:20}   {db_type_name:20}  {display_name:35}  '.format(a_model.ds_name,
                                                                          db_type_name=a_model.db_type,
                                                                          display_name = a_model.db_url
                                                                                           )
                      )
        else:
            print('No data source is found!')

        logging.getLogger('stanmo_logger').debug('discovered models: ' + model_list.__str__())
        return model_list


    def list_reflect_plugins(self):
        logger = logging.getLogger('stanmo_logger')
        logger.debug('looking for reflect engine' )
        plugin_spec_path = os.path.join(self.stanmo_home, self.MODEL_SPEC_PATH)
        logger = logging.getLogger('stanmo_logger')
        logger.debug('looking for model spec in path: ' + plugin_spec_path)
        spec_list = []

        for item in os.listdir(plugin_spec_path):
            if os.path.isdir(os.path.join(plugin_spec_path, item)):
                a_plugin = self.load_reflect_engine(item,plugin_spec_path = plugin_spec_path)
                spec_list.append(a_plugin)
        return spec_list

    def scan_reflect_plugins(self):
        plist = self.list_reflect_plugins()

        self.db_session.begin()
        self.db_session.query(dbmodels.MPlugin).delete()
        for plugin_dict in plist:
            self.db_session.add_all([
                dbmodels.MPlugin( plugin_name=plugin_dict['plugin_name'] ,
                                  module_name=plugin_dict['module_name'] ,
                                  plugin_spec_path=plugin_dict['plugin_spec_path'],
                                  supported_ds_types=plugin_dict['supported_ds_types'],
                                  sample_ds_url=plugin_dict['sample_ds_url'],
                                  author=plugin_dict['author'],
                                  plugin_desc=plugin_dict['plugin_desc'],
                                )
                                ])
        self.db_session.commit()

    def get_reflect_plugin(self, p_plugin_name = None):
        p = self.db_session.query(dbmodels.MPlugin).filter_by(plugin_name=p_plugin_name).first()
        return self.load_reflect_engine(p["module_name"])



    def load_reflect_engine(self, dottedpath, plugin_spec_path = None):

        assert dottedpath is not None, "dottedpath must not be None"
        #splitted_path = dottedpath.split('.')
        #modulename = '.'.join(splitted_path[:-1])
        #classname = splitted_path[-1]
        # print(sys.path)


        try:
            module = __import__(dottedpath, globals(), locals(), [])
            return {'reflectengine': module,
                    'plugin_name': getattr(module, 'plugin_name'),
                    'module_name': dottedpath,
                    'plugin_spec_path': plugin_spec_path,
                    'sample_ds_url': getattr(module, 'sample_ds_url'),
                    'plugin_desc': getattr(module, 'plugin_desc'),
                    'supported_ds_types': json.dumps(getattr(module, 'supported_ds_types')) ,
                    'author': getattr(module, 'author'),
                    }
        except AttributeError:
            logging.exception('load_reflect_engine: Could not import %s because the class was not found', dottedpath)
            return None


sf_app = SchemaIndexApp()