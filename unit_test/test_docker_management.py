# Main program required
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import app_helper
app_helper.initialize()

import logging
logger:logging.Logger = logging.getLogger(os.getenv('LOGGER_NAME'))

import time
import unittest

from knowsys.docker_management import DockerManager

config_test = app_helper.get_agent_config()
logger.info(f"config_test: {config_test}")



class TestDockerManagement(unittest.TestCase):
    def setUp(self):
        datapath = os.path.join(os.getcwd(), "unit_test", "_temp")
        self.docker_manager = DockerManager(datapath=datapath)
        self.kg_name = 'test_kg'


    def test_create(self):
        # start
        http_url, bolt_url = self.docker_manager.create_container(self.kg_name)
        self.assertTrue(http_url)
        self.assertTrue(bolt_url)
        
        kgs = self.docker_manager.list_running_KGs()
        print(f"(1) kgs: {kgs}")
        self.assertTrue(self.kg_name in [kg[0] for kg in kgs])


    def test_stop(self):
        # stop
        self.docker_manager.stop_KG(self.kg_name)
        kgs = self.docker_manager.list_running_KGs()
        print(f"(2) kgs: {kgs}")
        self.assertFalse(self.kg_name in [kg[0] for kg in kgs])


    def tearDown(self):
        self.docker_manager.stop_all()



if __name__ == '__main__':
    unittest.main()
