
import os,sys,threading,urllib.request,urllib.parse,urllib.error,math,json,oauth2client,ee,time,datetime

# cwd = '//166.2.126.25/rseat/Programs/FHTET_RTFD/Scripts/'
# cwd = 'Q:/rtfd_gee_compositing/'

##############################################################################################
#Returns all files containing an extension or any of a list of extensions
#Can give a single extension or a list of extensions
def glob(Dir, extension):
    Dir = check_end(Dir)
    if type(extension) != list:
        if extension.find('*') == -1:
            return [Dir + i for i in [i for i in os.listdir(Dir) if os.path.splitext(i)[1] == extension]]
        else:
            return [Dir + i for i in os.listdir(Dir)]
    else:
        out_list = []
        for ext in extension:
            tl = [Dir + i for i in [i for i in os.listdir(Dir) if os.path.splitext(i)[1] == ext]]
            for l in tl:
                out_list.append(l)
        return out_list
##############################################################################################
##############################################################################################
def check_end(in_path, add = '/'):
    if in_path[-len(add):] != add:
        out = in_path + add
    else:
        out = in_path
    return out
######################################################################################
def new_set_maker(in_list,threads):

    print (threads)
    out_sets =[]
    for t in range(threads):
        out_sets.append([])
    i =0
    for il in in_list:

        out_sets[i].append(il)
        i += 1
        if i >= threads:
            i = 0
    return out_sets
######################################################################################
##############################################################################################
def GetPersistentCredentials(credentials):
    tokens = json.load(open(credentials))
    refresh_token = tokens['refresh_token']
    # import ee
    credents = oauth2client.client.OAuth2Credentials(\
             None, '517222506229-vsmmajv00ul0bs7p89v5m89qs8eb9359.apps.googleusercontent.com', 'RUP0RZ6e0pPhDzsqIJ7KlNd1', refresh_token,\
             None, 'https://accounts.google.com/o/oauth2/token', None)
    return credents
credentials_dir = 'D:/rtfd_gee_compositing/eeCredentials/'
if os.path.exists(credentials_dir) == False: credentials_dir = 'Q:/rtfd_gee_compositing/eeCredentials/'
credentials = glob(credentials_dir,'')
credentials = [i for i in credentials if os.path.isdir(i) == False]
nCredentials = len(list(credentials))
##############################################################################################
def trackTasks(credential_name,id_list,task_count = 1):
	while task_count > 0:
		tasks = ee.data.getTaskList()
		tasks = [i for i in tasks if i['description'] in id_list]
		ready = [i for i in tasks if i['state'] == 'READY']
		running = [i for i in tasks if i['state'] == 'RUNNING']
		running_names = [[str(i['description']),str(datetime.timedelta(seconds = int(((time.time()*1000)-int(i['start_timestamp_ms']))/1000)))] for i in running]
		now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
		print(credential_name)
		print((len(ready),'tasks ready',now))
		print((len(running),'tasks running',now))
		print('Running names:')
		for rn in running_names:print(rn)
		print()
		print()
		time.sleep(5)
		task_count = len(ready) +len(running) 