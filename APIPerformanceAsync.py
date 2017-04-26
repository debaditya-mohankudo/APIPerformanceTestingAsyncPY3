
# coding: utf-8

# ##### Dependency
# 1. install 3rd party libs :socks, requests and custom lib GenCsr
# 2. python version = 3.6
# 3. Client auth cert of vice2 in pem format in the same directory
# 4. cacert.pem with all required ICAs and Roots in the same directory
# 
# Read more on concurrent.futures -> http://masnun.com/2016/03/29/python-a-quick-introduction-to-the-concurrent-futures-module.html
# 
# 

# ### import libs

# In[20]:

# std libs
import asyncio
import concurrent.futures as cf# async feature

import os
import random
import re
import socket
import sys
import time
# 3rd party libs- nees to be installed
import requests # HTTP requests - pip install requests
import socks # to send through vlabs tunnel - pip install pysocks
# home grown lib
from msslLib.GenCsr import GenCsr # Generates CSR




# In[22]:

def send_request_via_vlabs(port):
    """sends the requests through  socks tunnel
    """
    socks.setdefaultproxy(socks.PROXY_TYPE_SOCKS5,'127.0.0.1' , int(port))
    socket.socket = socks.socksocket
    print("socks proxy set for port:{port}".format(port=port))


# In[23]:

def get_random_str(n, prefix='', domain=''):
    """ generates a random alpha string of n chars and with a prefix
    """
    return ''.join([prefix, ''.join(random.sample('abcdefgnijklmnopqrstuvwxyz1234567890', n)), '.', domain])


# In[24]:

def custom_current_time():
    #return  time.perf_counter() - self.PERF_TIME_COUNTER_INIT + self.ABS_TIME
    #return time.perf_counter()
    return time.time()


# ### VICE2 Performance Check Class

# In[25]:

class VICE2PerformanceCheck():
    ''' class to test vice2 rest api performance/concurrency
    a certain no of parallel workers work on a pool of tasks
    Args:
        no_of_concurrent_threads - no of parallel workers
        no_of_req_per_prod - no of requests to send per certifiate product
        list_of_prod - list of products to enroll for
    '''
    
    def __init__(self, no_of_concurrent_threads, no_of_req_per_prod, list_of_prod):
        '''class initialization
        '''
        self.no_of_concurrent_threads = no_of_concurrent_threads # MAX REQUESTES TO BE SENT AT ONCE
        self.no_of_req = no_of_req_per_prod # NO OF REQUESTS FOR EACH PROD TYPE
        self.list_of_prod = list_of_prod # LIST OF CERT PRODUCT TYPES        
        
        self.session = requests.Session()
        
        # INFORMATION GATHERING
        time.perf_counter()
        self.ALL_RESPONSE_OBJECTS = []
        self.MASTER_INFO_LIST = []
        self.TOTAL_TIME_OF_EXECUTION = None
        self.ALL_DEBUG_STMT = ''
        self.PASS_LIST, self.FAIL_LIST = [], []
        self.LIST_ALL_TIME_OF_RESPONSE = []
        self.ABS_TIME = time.time()
        self.PERF_TIME_COUNTER_INIT = time.perf_counter() # more accurate than time.time()
        
        
        # api test data template
        self.api_testdata = {
            'certProductType': '',        # Private SSL
            'validityPeriod': '1Y',                     # '2Y, 3Y, 4Y
            #'specificEndDate': '11/03/2016',            # over rides validityPeriod
            'extraLicenses': '0',
            'firstName': 'kung-fu', 
            'lastName': 'panda',
            'email': 'wrwrw@dgdgdg.com',
            'challenge': 'P@ssword123',
            #'serverType': 'Extended Certificate Profile',
            'serverType': 'Microsoft',  
            'signatureAlgorithm': 'sha256WithRSAEncryptionFull' ,   
            'csr' : '',
            #'subject_alt_names': 'bbtest.net,2.bbtest.net',
            'ctLogOption': 'public'}
        
        


        
   
    def generate_csr_for_each_request(self):
        ''' generate csr for each request, 
            de-couples unique test data generation        
        '''        
        OU = time.ctime().replace(' ','-')
        L = 'Mountain view'
        S = 'California'
        C = 'US'
        counter = 0
        for i in range(int(self.no_of_req)):
            for prod in self.list_of_prod:
                counter += 1
                CN = get_random_str(7 ,prefix=CN_PREFIX + prod + str(counter), domain=DOMAIN) 
                csr = GenCsr(debug=False).type_RSA(CN, ORG, OU, L, S, C, 2048, 'SHA256')
                self.custom_print('\n{t}:::{c} as CN generating csr :::'.format(c=CN
                                                                                ,t=custom_current_time()))
                
                yield csr, prod
        
    
    def create_vice2_testdata_for_multiple_requests(self, no_of_requests, list_products_to_use):
        """ creates multiple request data for enrollment
            returns a list of dictionaries

            create_vice2_testdata_for_multiple_requests(2, ['Server', 'PrivateServer'])
        """
        api_testdata_list = []
        for csr, prod in self.generate_csr_for_each_request():
            self.api_testdata['csr'] = csr
            self.api_testdata['certProductType'] = prod
            api_testdata_list.append(dict(self.api_testdata))
    

        return api_testdata_list

    def send_api_request(self, api_testdata):
        """do client auth and send api request 
           returns a response object
        """
        #(ipadd, ca) = next(ip)
        #ipadd =
        return self.session.post('https://{base}/vswebservices/rest/services/enroll'.format(base=URL)
                                 , cert=CLIENT_CERT
                                 , data=api_testdata
                                 , verify='cacert.pem',
                                 #stream = True
                                )

    async def concurrent_execution(self, loop): 
        """executes a set of executions asynchronously"""
        set_of_vice2_requests = set()
        self.custom_print('\n{url} -> ip is {ip}'.format(url=URL, ip=socket.gethostbyname(URL)), to_print=True)
        self.custom_print('\n{t}:::Start preparing test data'.format(t=custom_current_time()), to_print=True)        
        
        
        api_testdata_list = self.create_vice2_testdata_for_multiple_requests(self.no_of_req, self.list_of_prod) # input data creation vice2
        
        self.custom_print('\n{t}:::All test data with unique csr is pre-generated , ready to post requests...'.format(
                t=custom_current_time()), 
                to_print=False)
        
        with cf.ThreadPoolExecutor(max_workers=self.no_of_concurrent_threads) as executor:            
            i =  custom_current_time() ## start time counter
            self.custom_print('\n{t}:::Start Sending requests now'.format(t=i), to_print=True)
         
            for api_testdata in api_testdata_list:                
                set_of_vice2_requests.add(loop.run_in_executor(executor, self.send_api_request, api_testdata))
            for future in set_of_vice2_requests:
                try:
                    resp = await future
                    self.ALL_RESPONSE_OBJECTS.append(resp)         
                except Exception as exc:
                    print('\ngenerated an exception: {s}'.format(s=exc))                   

        e = custom_current_time()  # measure the end time
        self.TOTAL_TIME_OF_EXECUTION = e - i
        self.custom_print('\n{f}\n{t}:::Finishing now::: \n'.format(t=e
                                                                    ,f= '-' * 40)
                                                                    ,to_print=True)




    def response_processing(self):
        ''' process all output response object and gather statistics
        '''    
        for response in self.ALL_RESPONSE_OBJECTS:
            temp = re.search('{p}<{s}>(.*?)</{s}>'.format(
                                 s='Transaction_ID',
                                 p='-----END CERTIFICATE-----</Certificate>'),                             
                             str(response.text), 
                             re.DOTALL)
             
            if temp:
                order_no = temp.group(1)
                status = 'PASS'
                debug_data = response.text[-80:-50]
            else:
                order_no = response.text
                status = 'FAIL'
                debug_data = response.request.body 

            info_per_request = (response.elapsed.total_seconds(), order_no, status, debug_data)
            self.MASTER_INFO_LIST.append(info_per_request)
            
            response.close() # close connection
            
        self.PASS_LIST = [item for item in self.MASTER_INFO_LIST if item[2] == 'PASS']
        self.FAIL_LIST = [item for item in self.MASTER_INFO_LIST if item[2] == 'FAIL']   
        for item in self.MASTER_INFO_LIST:
                self.LIST_ALL_TIME_OF_RESPONSE.append(item[0])
    
    def print_summary_and_write_to_log(self):
        ''' print summary of all requests,(both pass and fail)
        '''
        self.custom_print('\n{no}=Total no of request:::'.format(
                no=len(self.LIST_ALL_TIME_OF_RESPONSE)))
        self.custom_print('\n{conc}= Number of parallel workers:::'.format(
                conc=self.no_of_concurrent_threads))        
        self.custom_print('\n{actual}=Actual time for execution in seconds '.format(
                actual=self.TOTAL_TIME_OF_EXECUTION))        
        self.custom_print('\n{per}=time per request in secnds:::'.format(
                per=self.TOTAL_TIME_OF_EXECUTION/len(self.MASTER_INFO_LIST)))
        self.custom_print('\n{summ}=Sum of the duration of individual requests in seconds'.format(
                summ= sum(self.LIST_ALL_TIME_OF_RESPONSE)))
        self.custom_print('\n{minm}=Request that took minimum time in seconds '.format(
                minm =(min(self.LIST_ALL_TIME_OF_RESPONSE))))
        self.custom_print('\n{maxm}=Request that took maximum time in seconds\n '.format(
                maxm =(max(self.LIST_ALL_TIME_OF_RESPONSE))))
        self.custom_print('=' * 40, to_print=True)
        self.custom_print('\nPrinting  detailED summary\n') 
        self.custom_print('=' * 40 + '\n')
        self.write_results_into_file()
        
    def write_results_into_file(self):
        self.FAIL_LIST_log_format, self.PASS_LIST_log_format = '', ''
        for item in self.FAIL_LIST:
            self.FAIL_LIST_log_format += '{}\n'.format(item) 
        for item in self.PASS_LIST:
            self.PASS_LIST_log_format +=  '{}\n'.format(item) 
            
        if not os.path.isdir(LOG_DIR): os.mkdir(LOG_DIR)
        log_file_path = os.path.join('.', 
                                     LOG_DIR, 
                                     'perf_log_{t}_.txt'.format(t=str(time.time())))
        
        with open(log_file_path, 'w') as wr:
            wr.write(self.ALL_DEBUG_STMT)
            wr.write('\n')
            wr.write('time_taken_by_request ::: order ::: status\n')
            wr.write('\n{n}(Failed requests):::\n{ls}'.format(ls=self.FAIL_LIST_log_format, 
                                                              n=len(self.FAIL_LIST)))
            wr.write('\n{n}(Passed requests) :::\n{ls}'.format(ls=self.PASS_LIST_log_format,
                                                              n=len(self.PASS_LIST)))
        print('Log file path:::{p}'.format(p=os.path.abspath(log_file_path)))

    def custom_print(self, text, to_print=False, to_log=True):
        '''custom print utility'''
        if to_print:
            print(text)
        if to_log:
            self.ALL_DEBUG_STMT += str(text)
            

        


# ### Environment and Account Information

# In[26]:

ORG = 'hihowru-2011-1' 


URL = 'hi.net' 


CLIENT_CERT = 'clientcert.pem'  # pem format - need to create from pfx - see documentation


DOMAIN = 'hey.net'

CN_PREFIX = 'nothing'

LOG_DIR = 'logs_dir'


# ### Set Performance requirements

# In[27]:

VICE2_REQUESTS_FOR_EACH_PROD = 50
LIST_PRODUCTS_TO_ENROLL = ['prod']
CONCURRENCY_VICE2 = 50 # MAX 4 REQUESTS WILL BE SENT AT A TIME - THROTTLE


# ### Execution

# In[28]:

print('Starting Concurrent Execution...')
# take advanatage of windows specific network connection ( OPTIONAL)
if sys.platform == 'win32':
    print('Windows Platform')
    loop = asyncio.ProactorEventLoop() 
    asyncio.set_event_loop(loop)
if 'linux' in sys.platform:
    import uvloop  # pip install uvloop
    print('*nix Platform')
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    

p = VICE2PerformanceCheck(CONCURRENCY_VICE2, VICE2_REQUESTS_FOR_EACH_PROD, LIST_PRODUCTS_TO_ENROLL)
#send_request_via_vlabs(8899)
loop = asyncio.get_event_loop()       
loop.run_until_complete(p.concurrent_execution(loop))
loop.close()
p.response_processing()
p.print_summary_and_write_to_log()
print('Finished Execution....')


# In[ ]:



