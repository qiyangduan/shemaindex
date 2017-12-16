import tornado.web
import json

from dbmodels import engine, MDatasource,MTable,MColumn

from schemaindexapp import si_app
from sqlalchemy.orm import create_session


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

class OverviewHandler(tornado.web.RequestHandler):
    def get(self):
        # self.write("Hello, world")
        # print('overview ed')
        session = create_session(bind=engine)
        dbrs = si_app.get_data_source_rs()

        ds_count = dbrs.count()
        tab_count = session.query(MTable).count()
        attr_count = session.query(MColumn).count()
        base_navigation_dict = {'selected_menu': 'overview',
                                'dbrs': dbrs,
                                'plugin_list': si_app.get_plugin_list(),
                                'ds_count':str(ds_count),
                                'tab_count':str(tab_count),
                                'attr_count':str(attr_count),
                                'tag_count':'NA',

        }

        self.render("overview.html", base_navigation_dict=base_navigation_dict)

class DatabaseSummaryHandler(tornado.web.RequestHandler):
    def get(self):
        # self.write("Hello, world")
        # param_db_name = self.get_argument("table_group_name", None)
        session = create_session(bind=engine)
        param_ds_name = self.get_argument("ds_name", None)
        if param_ds_name is None:
            print('error: no schema name is given')
            base_navigation_dict = {'selected_menu': 'datasources',
                                    'dbrs': session.query(MDatasource),
                                    'error': 'error: no schema name is given',
                                    'db': None
                                    }
            # self.render("404.html")
            self.render("database_summary.html",  # current_schema_name = param_schema_name,
                        base_navigation_dict=base_navigation_dict )

        entry = None

        dbrs1 = session.query(MDatasource).filter_by(ds_name = param_ds_name )
        db = dbrs1.first()
        if db is None:
            print('error: did not find database')

        dbrs = si_app.get_data_source_rs()
        tabrs = si_app.get_table_list_for_data_source_rs(param_ds_name= param_ds_name)



        base_navigation_dict = {'selected_menu': 'datasources',
                                'dbrs': dbrs,
                                'selected_schema_name': param_ds_name,
                                'db':db,
                                'tabrs':tabrs,
                                'plugin_name_list': si_app.get_plugin_name_list(),
                                }

        self.render("database_summary.html", # current_schema_name = param_schema_name,
                    base_navigation_dict=base_navigation_dict # ,dbrs=dbrs, tabrs=tabrs,db=db
                    )

    def post(self):
        ds_dict = {}
        ds_dict['table_group_name']  = self.get_argument('table_group_name')
        ds_dict['ds_name'] = self.get_argument('ds_name')
        ds_dict['ds_url'] = self.get_argument('ds_url')
        ds_dict['ds_type'] = self.get_argument('ds_type')
        ds_dict['ds_desc'] = self.get_argument('ds_desc')

        db = si_app.update_data_soruce(ds_dict)


        dbrs = si_app.get_data_source_rs()

        Info = {'result': 'ok', 'message':'A new data source is updated.'}
        base_navigation_dict = {'selected_menu': 'database',
                                'dbrs': dbrs,
                                'selected_add_data_source':True, 'selected_schema_name':ds_dict['ds_name'],
                                'plugin_name_list': si_app.get_plugin_name_list(),
                                'db':db
                                }
        self.render("database_summary.html",
                    base_navigation_dict=base_navigation_dict,
                    info=Info, dbrs=dbrs, db = None,tabrs=None)


class GlobalSearchHandler(tornado.web.RequestHandler):
    def get(self):
        q = ''
        res = []
        dbrs = si_app.get_data_source_rs()

        base_navigation_dict = {'selected_menu': 'search',
                                'dbrs': dbrs,
                                'selected_schema_name': ''
                                }
        self.render("global_search_result.html",
                    dbrs=dbrs,
                    q=q,
                    base_navigation_dict=base_navigation_dict,
                    search_result = res)

    def post(self):

        q = self.get_argument('q')
        res = si_app.global_whoosh_search(q)
        dbrs = si_app.get_data_source_rs()

        base_navigation_dict = {'selected_menu': 'search',
                                'dbrs': dbrs,
                                'selected_schema_name': ''
                                }
        self.render("global_search_result.html",
                    dbrs=dbrs,
                    q=q,
                    base_navigation_dict=base_navigation_dict,
                    search_result = res)





class AddDataSourceHandler(tornado.web.RequestHandler):
    def get(self):
        # json.dumps()
        base_navigation_dict = {'selected_menu': 'datasources',
                                'dbrs': si_app.get_data_source_rs(),
                                'plugin_name_list': si_app.get_plugin_name_list(),
                                'selected_add_data_source':True,
                                'input_ds_param':True,
                                'selected_schema_name':'__add_data_source__',
                                }
        ds_type = self.get_argument('ds_type',default=None)
        if ds_type is not None:
            base_navigation_dict['input_db_type'] = ds_type
            base_navigation_dict['input_ds_param'] = si_app.get_plugin_info(p_plugin_name=ds_type)

        self.render("database_summary.html",
                    base_navigation_dict=base_navigation_dict,
                      db=None,tabrs=None)


    def post(self):
        ds_dict = {}
        ds_dict['table_group_name']  = self.get_argument('table_group_name')
        ds_dict['ds_name'] = self.get_argument('ds_name')
        ds_dict['ds_url'] = self.get_argument('ds_url')
        ds_dict['ds_type'] = self.get_argument('ds_type')
        ds_dict['ds_desc'] = self.get_argument('ds_desc')
        ds_dict['db_comment'] = self.get_argument('db_comment')

        db = si_app.add_data_soruce(ds_dict)
        if db:
            self.redirect('/database_summary?ds_name=' + ds_dict['ds_name'])
        else:
            dbrs = si_app.get_data_source_rs()

            Info = {'result': 'ok', 'message': 'A new data source is added.'}
            base_navigation_dict = {'selected_menu': 'database',
                                    'dbrs': dbrs,
                                    'selected_add_data_source': True,
                                    'plugin_name_list': si_app.get_plugin_name_list(),
                                    'selected_schema_name': ds_dict['ds_name'],
                                    'db': db,
                                    }
            self.render("database_summary.html",
                        base_navigation_dict=base_navigation_dict)

        '''
        dbrs = si_app.get_data_source_rs()

        Info = {'result': 'ok', 'message':'A new data source is added.'}
        base_navigation_dict = {'selected_menu': 'database',
                                'dbrs': dbrs,
                                'plugin_name_list': si_app.get_plugin_name_list(),
                                'selected_schema_name':ds_dict['ds_name'],
                                'db':db,
                                }
        self.render("database_summary.html",
                    base_navigation_dict=base_navigation_dict)
        '''

class DeleteDataSourceHandler(tornado.web.RequestHandler):
    def post(self):
        ds_dict = {}
        ds_dict['ds_name'] = self.get_argument('ds_name')
        ds_dict['delete_reflected_database_automatic'] = self.get_argument('delete_reflected_database_automatic', default=None)

        # print ds_dict['delete_reflected_database_automatic']
        result_message = si_app.delete_data_soruce(ds_dict)

        dbrs = si_app.get_data_source_rs()
        base_navigation_dict = {'selected_menu': 'database',
                                'dbrs': dbrs,
                                'selected_add_data_source':True,
                                'plugin_name_list': si_app.get_plugin_name_list(),
                                'selected_schema_name':ds_dict['ds_name'],
                                'message': result_message
                                }
        if result_message['message_title']  == 'Error':
            session = create_session(bind=engine)
            dbrs1 = session.query(MDatasource).filter_by(ds_name = ds_dict['ds_name'])
            db = dbrs1.first()
            base_navigation_dict['db'] = db
            base_navigation_dict['tabrs'] = si_app.get_table_list_for_data_source_rs(param_ds_name= ds_dict['ds_name'])


        self.render("database_summary.html",
                    base_navigation_dict=base_navigation_dict)




class ReflectDataSourceHandler(tornado.web.RequestHandler):

    def post(self):
        ds_name = self.get_argument('ds_name')
        si_app.reflect_db(ds_name)
        # self.__setattr__('reflected_db', ds_name)
        self.redirect('/database_summary?ds_name='+ds_name)


class ViewTableInNotebookHandler(tornado.web.RequestHandler):
    def get(self):
        # json.dumps()
        table_name = self.get_argument('table_name')
        ds_name = self.get_argument('ds_name')
        session = create_session(bind=engine)
        ds_url = None
        dbrs = session.query(MDatasource).filter_by(ds_name=ds_name)
        for row in dbrs:
            ds_url =  row.ds_url
        if ds_url is None:
            print('error: database not found')

        #repls = {'hello': 'goodbye', 'world': 'earth'}
        #s = 'hello, world'
        #reduce(lambda a, kv: a.replace(*kv), repls.iteritems(), s)

        replace_dict = {'$$TABLE$$': table_name,
                        '$$DB_URL$$': ds_url}

        with open("/home/duan/github/show_table_template.ipynb", "rt") as fin:
            with open("/home/duan/github/show_table_t_" + table_name + ".ipynb", "wt") as fout:
                for line in fin:
                    # fout.write(line.replace('$$TABLE$$', table_name))
                    fout.write(reduce(lambda a, kv: a.replace(*kv), replace_dict.iteritems(), line))

        '''
                import subprocess # /media/adata/linux/anaconda27/bin/
                subprocess.call(["jupyter", "notebook",  "/home/duan/github/show_table_t_" + table_name + ".ipynb"])
        '''
        from subprocess import Popen
        p = Popen(["jupyter", "notebook",  "/home/duan/github/show_table_t_" + table_name + ".ipynb"]) # something long running

        Info = {'result': 'started in another browser'}
        self.write(json.dumps(Info))









class DatabaseJSONHandler(tornado.web.RequestHandler):
    def post(self):
        ds_dict = {}
        ds_dict['table_group_name']  = self.get_argument('table_group_name')
        ds_dict['ds_name'] = self.get_argument('ds_name')
        ds_dict['ds_url'] = self.get_argument('ds_url')
        ds_dict['ds_type'] = self.get_argument('ds_type')

        si_app.add_data_soruce(ds_dict)


        Info = {'result': 'ok'}
        self.write(json.dumps(Info))

    def get(self):
        # json.dumps()
        db_dict = si_app.get_data_source_name_list()
        self.write(json.dumps(db_dict)) # data = json.dumps(db_dict)

class SearchSuggestionJSONHandler(tornado.web.RequestHandler):
    def get(self):
        q = self.get_argument('query')
        res = si_app.get_whoosh_search_suggestion(q)
        self.write(json.dumps(res))

class JSON1Handler(tornado.web.RequestHandler):
    def get(self):
        q = self.get_argument('query')
        res = si_app.get_whoosh_search_suggestion(q)
        self.write(json.dumps(res))

        # self.write(json.dumps(res1))

class hdfs_inotify_get_checkpoint_txid(tornado.web.RequestHandler):
    def get(self):
        self.write('890')
        return
        data_source_name = self.get_argument('data_source_name')
        ds_dict = si_app.get_data_source_dict(ds_name=data_source_name)
        self.write(str(ds_dict['db_trx_id']))
        # self.write('-1')

class hdfs_inotify_change(tornado.web.RequestHandler):
    def post(self):
        event_type = self.get_argument('event_type')
        if event_type  == 'CREATE':
            path = self.get_argument('path')
            owner = self.get_argument('owner')
            date_time = self.get_argument('date_time')
            txid = self.get_argument('txid')
            data_source_name = self.get_argument('data_source_name')

            doc_old = si_app.global_whoosh_search_by_id(q_id=path)
            if len(doc_old) > 0:
                si_app.logger.error('the doc/entity already not exist for creation event.')
                si_app.delete_doc_from_index_by_docnum(p_docnum=doc_old[0]['docnum'])

            si_app.add_table_content_index(ds_name = data_source_name,
                                           table_id=path,
                                           table_info=json.dumps({'path':path, 'date_time':date_time}),
                                           )
            # si_app.commit_index()
            print('event_type', event_type, "time", date_time,'tx:', txid)

        # Do the thing
        elif event_type == 'UNLINK':
            path = self.get_argument('path')
            date_time = self.get_argument('date_time')
            txid = self.get_argument('txid')
            data_source_name = self.get_argument('data_source_name')

            doc_old = si_app.global_whoosh_search_by_id(q_id=path)
            if len(doc_old) < 1:
                si_app.logger.error('the doc/entity to delete/unlink does not exist.')
            else:
                si_app.delete_doc_from_index_by_docnum(p_docnum=doc_old[0]['docnum'])

            # si_app.commit_index()

            print('event_type', event_type, "time", date_time, 'tx:', txid)
        if event_type in 'RENAME':
            src_path = self.get_argument('src_path')
            dst_path = self.get_argument('dst_path')
            date_time = self.get_argument('date_time')
            txid = self.get_argument('txid')
            data_source_name = self.get_argument('data_source_name')

            doc_old = si_app.global_whoosh_search_by_id(q_id=src_path)
            if len(doc_old) < 1:
                si_app.logger.error('the doc/entity to rename does not exist.')
            else:
                si_app.delete_doc_from_index_by_docnum(p_docnum=doc_old[0]['docnum'])

            si_app.add_table_content_index(ds_name = data_source_name,
                                           table_id=dst_path,
                                           table_info=json.dumps({'path':dst_path, 'date_time':date_time}),
                                           )
            # si_app.commit_index()
            path = src_path + '.....' + dst_path
            print('event_type', event_type,'path',path, "time", date_time,'tx:', txid)
        else:
            print('event_type', event_type )

        print(path)
        self.write('received!' + path)