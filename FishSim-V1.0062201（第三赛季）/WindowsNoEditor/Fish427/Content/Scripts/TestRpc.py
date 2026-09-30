from xmlrpc.server import SimpleXMLRPCServer
from socketserver import ThreadingMixIn
import unreal_engine as ue
import threading
from cyclonedds.core import Qos, Policy
rpc_server = "127.0.0.1"
rpc_port = 8008

class TestRpc:

    
    def run_server(self):
        server = SimpleXMLRPCServer((rpc_server, rpc_port))
        server.register_function(self.get_name, "get_name")
        print("runserver...")
        server.serve_forever()
    def begin_play(self):
        print('begin_play')
        
        

        

        print("Listening on port 8000...")
        server_thread = threading.Thread(target=self.run_server)
        server_thread.daemon = True  
        server_thread.start()
              
        print("Listeninginging on port 8000...")
    def get_name(self,name):
            res = f"name111:{name}"
            teststr = self.uobject.get_owner().call_function('getfishinfor')
            return res
    