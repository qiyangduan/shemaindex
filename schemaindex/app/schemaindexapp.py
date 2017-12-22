from __future__ import unicode_literals
# according to http://python-future.org/compatible_idioms.html#unicode-text-string-literals
#
#
# #import atexit
import os
import shutil
import logging
import json
import time
import importlib
from builtins import str


from sqlalchemy import Column, DateTime, String, Integer, func
from sqlalchemy import create_engine
from sqlalchemy.orm import create_session


from whoosh import index
from whoosh.qparser import QueryParser
from whoosh.fields import *


from .config import cfg
from .dbmodels import MColumn, MTable, MDatasource, MPlugin, Base

#sys.path.append( cfg['main']['schemaflex_spec'])

import sqlite3

si_db_engine =  create_engine('sqlite:///' + cfg['database']['sqlite_file'])


class SchemaIndexApp:
    """ The runtime platform for running all mining models
    """

    MODEL_DATAFRAME_DIR = 'data'
    MODEL_INSTANCE_DIR = 'instance'
    MODEL_SPEC_DIR = 'plugin' # Save the specs of a specific model, including file mining_model.json
    MODEL_SPEC_PATH = 'plugin' # Save all model_spec programs. One plugin may serve multiple models
    MODEL_SPEC_FILENAME = 'mining_model.json'
    TIME_FORMATER = "%Y-%m-%d %H:%M:%S"

    config = cfg
    stanmo_home = cfg['main']['schemaflex_home']

    logger = logging.getLogger('stanmo_logger')

    indexdir = cfg['main']['schemaflex_text_index_path']
    ix = None
    index_writer = None

    data_source_dict = {} # {'__sample__': {}}

    db_session = create_session(bind=si_db_engine)
    data_source_process = {} #  {'__sample__': []}
    time_to_commit = time.time()


    def __init__(self):
        # Add the plugin (model specs) home to sys path for dynamic loading all model specs defined under $STANMO_HOME/plugin
        # sys.path.append(os.path.join(self.stanmo_home, self.MODEL_SPEC_PATH))

        self.schemaindex_init()
        #
        #self.datasource_init() # Calling here cause troubles to __import__, weird. 20171222

        self.logger.debug('SchemaIndex platform is started.')


    def schemaindex_init(self):

        db_file_path = cfg['database']['sqlite_file']
        to_init_indicator = db_file_path #   cfg['main']['init_indicator_file']
        self.logger.debug('Checking where to re-init by file:' + to_init_indicator)

        if os.path.exists(to_init_indicator):
            self.logger.debug('DB file is ready, no re-init, going to normal startup.')
            return;

        self.logger.debug('SchemaIndex platform is being initialized because there no data file yet.')
        # os.remove(to_init_indicator)

        try:

            if os.path.exists(db_file_path):
                self.logger.debug('Trying to remove existing db file.')
                os.remove(db_file_path)



            # recreate the sqlite database file
            self.logger.debug('creating db at ...:  ' + db_file_path)
            engine = create_engine('sqlite:///' + db_file_path)
            Base.metadata.create_all(engine)

            self.logger.debug('scanning plugins for re-initialization... ')
            self.scan_reflect_plugins()
        except Exception as e:
            print(str(e))
            self.logger.debug('init error: ' + str(e))  # will not print anything

        self.logger.debug('re-construct text index at folder: ' + self.indexdir)  # will not print anything
        if os.path.exists(self.indexdir):
            shutil.rmtree(self.indexdir)
        os.mkdir(self.indexdir)

        schema = Schema(ds_name=ID(stored=True), table_id=ID(stored=True), table_info=TEXT(stored=True)) # , column_info=TEXT(stored=True)
        ix = index.create_in(self.indexdir , schema)
        print("schemaindex platform is re-initialized, with new sqlite data file and whoosh index." )  # will not print anything


    def datasource_init(self):

        self.logger.debug('SchemaIndex is trying to boot up all init service by each data source ...')
        ds_list = self.get_data_source_rs()

        # Here we loop through all data sources. For each of them, if it is not cached, then it is the first time to run schemaindexapp.
        # We do 2 things for each data source
        # 1. cache the ds_dict
        # 2. run datasource_init of each datasource as defined by plugin.
        for row in ds_list:
            if row.ds_name not in self.data_source_dict.keys() :
                self.data_source_dict[row.ds_name] = self.get_data_source_dict(ds_name=row.ds_name)

                the_engine = self.get_reflect_plugin(p_plugin_name=row.ds_type)['reflect_engine']
                one_ds = the_engine.ReflectEngine(ds_dict = row.to_dict())
                one_ds.datasource_init()

            '''
            the_engine= si_app.get_reflect_plugin(row.ds_type)
            a_ds = the_engine.ReflectEngine(ds_dict = self.get_data_source_dict(ds_name= row.ds_name) ) #SQLAlchemyReflectEngine()
            a_ds.reflect(reload_flag=True)
            '''

    def __del__(self):
        if self.index_writer is not None:
            # print('closing index')
            self.index_writer.cancel()
            self.ix.close() #


    def delete_data_soruce(self,ds_dict = None):
        session = create_session(bind=si_db_engine)
        session._model_changes={}

        tab_result = session.query(MTable).filter_by(ds_name=ds_dict['ds_name'])
        if tab_result.count() > 0 and (not ds_dict['delete_reflected_database_automatic'] == 'on'):
            return {'message_type': 'danger',
                    'message_title': 'Error',
                    'message_body':'the data source "' + ds_dict['ds_name'] + '" contains metadata. Please check " Delete Contents in Data Source" and try again'}

        session.begin()
        session.query(MDatasource).filter_by(ds_name=ds_dict['ds_name']).delete(synchronize_session=False)
        session.query(MTable).filter_by(ds_name=ds_dict['ds_name']).delete(synchronize_session=False)
        session.query(MColumn).filter_by(ds_name=ds_dict['ds_name']).delete(synchronize_session=False)
        session.commit()
        self.delete_doc_from_index_by_datasource(ds_name=ds_dict['ds_name'])

        return {'message_type': 'info',
                'message_title': 'Info',
                'message_body': 'the data source "' + ds_dict['ds_name'] + '" is deleted.'}

    def add_data_soruce(self,ds_dict = None):
        session = create_session(bind=si_db_engine)
        session._model_changes={}

        session.begin()
        session.add_all([
            MDatasource(
                               ds_name=ds_dict['ds_name'] ,
                               ds_type=ds_dict['ds_type'] ,
                               ds_param=json.dumps(ds_dict['ds_param']) ,
                               nbr_of_tables=0,
                               nbr_of_columns=0,
                               ds_desc=ds_dict['ds_desc'],
                               created_date = func.now(),
                    )
        ])
        session.commit()
        dbrs1 = session.query(MDatasource).filter_by(ds_name=ds_dict['ds_name'])
        db = dbrs1.first()
        if db is None: # This should not happend!
            si_app.logger.error('error: did not find database')
            return False
        return True

    def update_data_soruce_trx_id(self,ds_name = None, trx_id = None):

        current_time = time.time()
        self.data_source_dict[ds_name]['ds_param']['inotify_trx_id'] = trx_id
        if current_time - self.time_to_commit > self.config['main']['interval_commit_trx_id']:
            self.logger.info('time out, this time write to database')
            self.update_data_soruce(ds_dict=self.data_source_dict[ds_name])
            self.time_to_commit = current_time


    def update_data_soruce(self,ds_dict = None):

        self.data_source_dict[ds_dict['ds_name']] = ds_dict

        session = create_session(bind=si_db_engine)
        session._model_changes={}
        session.begin()
        session.query(MDatasource).filter_by(ds_name=ds_dict['ds_name']).\
            update({
                    'ds_type': ds_dict['ds_type'],
                    'ds_param': json.dumps(ds_dict['ds_param']),
                    'ds_desc':ds_dict['ds_desc']})


        session.commit()
        dbrs1 = session.query(MDatasource).filter_by(ds_name=ds_dict['ds_name'])
        db = dbrs1.first()
        if db is None:
            print('error: did not find database')
        return db


    '''
        def get_data_source_name_list(self):
    
            rs = self.db_session.query(MDatasource) #.filter_by(name='ed')
    
            ds_list = []
            for row in rs:
                ds_list.append({'name': row.ds_name , 'ds_type': row.ds_type } )
            return  ds_list
    '''
    def global_whoosh_search(self, q = ''):

        ix = index.open_dir(self.indexdir)
        res = []
        with ix.searcher() as searcher:
            query = QueryParser("table_info", ix.schema).parse(q)
            results = searcher.search(query)
            for r in results:
                res.append({'ds_name': r['ds_name'],
                            'docnum': r.docnum,
                            'table_info': r['table_info'],
                            })

        return res

    def global_whoosh_search_by_id(self, q_id = ''):

        ix = index.open_dir(self.indexdir)
        res = []
        with ix.searcher() as searcher:
            query = QueryParser("table_id", ix.schema).parse(q_id)
            results = searcher.search(query)
            for r in results:
                res.append({'ds_name': r['ds_name'],
                            'docnum': r.docnum,
                            'table_info': r['table_info'],
                            })

        return res

    def delete_doc_from_index_by_docnum(self, p_docnum = None):

        ix = index.open_dir(self.indexdir)
        index_writer = ix.writer()

        index_writer.delete_document(docnum = p_docnum)
        index_writer.commit()
        return True

    def delete_doc_from_index_by_datasource(self, ds_name = None):

        ix = index.open_dir(self.indexdir)
        index_writer = ix.writer()

        ix = index.open_dir(self.indexdir)
        res = []
        with ix.searcher() as searcher:
            query = QueryParser("ds_name", ix.schema).parse(ds_name)
            num = index_writer.delete_by_query(q=query)
            si_app.logger.info( '{0:10} documents from data source {1:15}  '.format( str(num), ds_name) )

        index_writer.commit()
        return True



    def get_whoosh_search_suggestion(self, q = ''):

        indexdir = self.indexdir
        ix = index.open_dir(indexdir)

        result = []
        with ix.reader() as r:
            for aterm in r.most_frequent_terms("table_info", number=5, prefix=q):
                one_result = aterm[1].decode('utf-8')
                result.append(one_result) # The result was like (1.0, 'dept_manager'), but here i need only a keyword
                #print(aterm)

        return result


    def add_table_content_index(self,ds_name = None, table_id = None, table_info = None):

        ix = index.open_dir(self.indexdir)
        index_writer = ix.writer()
        # index_writer.add_document(ds_name = unicode(ds_name), table_id=unicode(table_id), table_info=unicode(table_info))

        index_writer.add_document(ds_name = str(ds_name), table_id=str(table_id), table_info=str(table_info))
        index_writer.commit()

    def commit_index(self, table_id=None, table_info=None):
        return
        self.index_writer.commit()
        self.ix = index.open_dir(self.indexdir)
        self.index_writer = self.ix.writer()



    def get_data_source_rs(self):

        rs = self.db_session.query(MDatasource).order_by(MDatasource.ds_name.asc()) #.filter_by(name='ed')
        return rs

    def get_data_source_dict(self, ds_name = None):

        if ds_name in self.data_source_dict.keys() is not None:
            return self.data_source_dict[ds_name]

        rs = self.db_session.query(MDatasource).filter_by(ds_name=ds_name)
        if rs.count() > 0:
            ds = rs.first()
            self.data_source_dict[ds_name] = ds.to_dict() # {x.name: getattr(ds, x.name) for x in ds.__table__.columns}
            return self.data_source_dict[ds_name]
        return None

    def get_plugin_name_list(self):
        plugins = []
        rs = self.db_session.query(MPlugin)
        for p in rs:
            plugins.append(p.plugin_name)
        return  plugins

    def get_plugin_list(self):
        plugins = []
        rs = self.db_session.query(MPlugin)
        for p in rs:
            plugins.append(p)
        return  plugins

    def get_plugin_info(self, p_plugin_name = ''):

        p = self.db_session.query(MPlugin).filter_by(plugin_name=p_plugin_name).first()
        # p['ds_param'] = json.loads(p.ds_param )
        return  p


    def get_reflect_plugin(self, p_plugin_name = None):
        p = self.db_session.query(MPlugin).filter_by(plugin_name=p_plugin_name).first()
        return self.load_reflect_engine(p.module_name)


    def get_table_list_for_data_source_rs(self, param_ds_name = ''):
        sql = '''
                SELECT c.ds_name,  c.table_name, t.table_comment, group_concat(c.column_name)   as column_names
                FROM mcolumn c, mtable t
                where c.table_name = t.table_name and c.ds_name = t.ds_name and t.ds_name = \'''' + param_ds_name + '''\'
                GROUP BY c.ds_name, c.table_name;
                '''

        tabrs = si_db_engine.execute(sql)
        return  tabrs


    def reflect_db(self,data_source_name=None):
        session = create_session(bind=si_db_engine)
        dbrs = session.query(MDatasource).filter_by(ds_name=data_source_name)
        for row in dbrs:
            the_engine= si_app.get_reflect_plugin(row.ds_type)['reflect_engine']
            a_ds = the_engine.ReflectEngine(ds_dict = self.get_data_source_dict(ds_name= row.ds_name) ) #SQLAlchemyReflectEngine()
            a_ds.reflect(reload_flag=True)

            session_update = create_session(bind=si_db_engine)
            session_update.begin()
            session_update.query(MDatasource).filter_by(ds_name=row.ds_name).\
                update({'last_reflect_date': func.now()}, synchronize_session='fetch')
            session_update.commit()
            session_update.close()
        session.close()



    def list_data_sources(self):
        model_list = []
        models = []

        session = create_session(bind=si_db_engine)
        dbrs = session.query(MDatasource)  # .filter_by(name='ed')


        for db in dbrs:
                models.append(db)
        if len(models) > 0:
            print('{0:20}   {1:20}  {2:35}  '.format('data source name',
                                                                           'data source type',
                                                                           'URL'
                                                                           ))
            for a_model in models:
                print('{0:20}   {db_type_name:20}  {table_group1_name:35}  '.format(a_model.ds_name,
                                                                          db_type_name=a_model.ds_type,
                                                                          table_group1_name = a_model.ds_param
                                                                                           )
                      )
        else:
            print('No data source is found!')

        logging.getLogger('stanmo_logger').debug('discovered models: ' + model_list.__str__())
        return model_list


    def list_reflect_plugins(self):
        logger = logging.getLogger('stanmo_logger')
        logger.debug('looking for reflect engine from location: ' + os.path.join(self.stanmo_home, self.MODEL_SPEC_PATH) )
        plugin_spec_path = os.path.join(self.stanmo_home, self.MODEL_SPEC_PATH)
        logger = logging.getLogger('stanmo_logger')
        logger.debug('looking for model plugin in path: ' + plugin_spec_path)
        spec_list = []

        for item in os.listdir(plugin_spec_path):
            if os.path.isdir(os.path.join(plugin_spec_path, item)):
                a_plugin = self.load_reflect_engine(item,plugin_spec_path = plugin_spec_path)
                spec_list.append(a_plugin)
        return spec_list

    def scan_reflect_plugins(self):
        plist = self.list_reflect_plugins()

        self.db_session.begin()
        self.db_session.query(MPlugin).delete()
        for plugin_dict in plist:
            if plugin_dict is not None:
                self.db_session.add_all([
                    MPlugin( plugin_name=plugin_dict['plugin_name'] ,
                                      module_name=plugin_dict['module_name'] ,
                                      plugin_spec_path=plugin_dict['plugin_spec_path'],
                                      ds_param=json.dumps(plugin_dict['ds_param']),
                                      supported_ds_types=plugin_dict['supported_ds_types'],
                                      notebook_template_path=plugin_dict['notebook_template_path'],
                                      sample_ds_url=plugin_dict['sample_ds_url'],
                                      author=plugin_dict['author'],
                                      plugin_desc=plugin_dict['plugin_desc'],
                                    )
                                    ])
        self.db_session.commit()



    def load_reflect_engine(self, dottedpath, plugin_spec_path = None):

        assert dottedpath is not None, "dottedpath must not be None"
        #splitted_path = dottedpath.split('.')
        #modulename = '.'.join(splitted_path[:-1])
        #classname = splitted_path[-1]
        # print(sys.path)


        try:
            module = __import__(dottedpath, globals(), locals(), [])
            return {'reflect_engine': module,
                    'module_name': dottedpath,
                    'plugin_name': getattr(module, 'plugin_name'),
                    'ds_param': getattr(module, 'ds_param'),
                    'plugin_spec_path': plugin_spec_path,
                    'notebook_template_path': getattr(module, 'notebook_template_path'),
                    'sample_ds_url': getattr(module, 'sample_ds_url'),
                    'plugin_desc': getattr(module, 'plugin_desc'),
                    'supported_ds_types': json.dumps(getattr(module, 'supported_ds_types')) ,
                    'author': getattr(module, 'author'),
                    }
        except Exception as e:
            self.logger.error( "load_reflect_engine (error): Failed to import plugin %s, due to error :{%s}" % (dottedpath, e) )
            return None


si_app = SchemaIndexApp()
