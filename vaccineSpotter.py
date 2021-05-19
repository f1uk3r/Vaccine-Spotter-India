import requests
from datetime import date,datetime,timedelta
import logging
from time import time,ctime
import yaml

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
										filename='vaccine.log',
										level = logging.DEBUG)
logger = logging.getLogger()
class vaccineSpotter:
	def __init__(self, config_file_path, time_delay=1):
		self.config_file_path = config_file_path
		self.time_delay = time_delay
		self.cfg = self.read_config()
		self.set_params()
		self.previous_result = None
		self.telegram_info = None
		self.session_id_dictionary = {}
		self.headers = {'User-Agent': "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:87.0) Gecko/20100101 Firefox/87.0"}

	def read_config(self):
		with open(self.config_file_path, "r") as ymlfile:
			cfg = yaml.safe_load(ymlfile)
		return cfg
		
	def set_params(self):
		## params
		self.area_info = self.cfg["area_info"]

		## area code
		self.__district_code = self.area_info['__district_code']
		self.__pincode = self.area_info['__pincode']

		## age limit for vaccination
		self.age_limit_info = self.cfg['age_limit']
		self.age_limit = self.age_limit_info['age_limit']

		## telegram info
		self.telegram_info = self.cfg['telegram']
		self.telegram_token = self.telegram_info['token']
		self.telegram_channel_18 = self.telegram_info['channel_18']
		self.telegram_channel_45 = self.telegram_info['channel_45']
		self.base = f'https://api.telegram.org/bot{self.telegram_token}/'

	def send_telegram_msg_18(self, result_str):
		url = self.base + f'sendMessage?chat_id=@{self.telegram_channel_18}&text={result_str}'
		print(url)
		if result_str is not None:
			response = requests.get(url, headers=self.headers)
			print(f'response from telegram 18+ channel: {response}')

	def send_telegram_msg_45(self, result_str):
		url = self.base + f'sendMessage?chat_id=@{self.telegram_channel_45}&text={result_str}'
		print(url)
		if result_str is not None:
			response = requests.get(url, headers=self.headers)
			print(f'response from telegram 45+ channel: {response}')

	def parse_json_district_code(self, result):
		output_18 = []
		output_45 = []
		centers = result['centers']
		for center in centers:
			sessions = center['sessions']
			for session in sessions:
				if not self.session_id_dictionary.get(session['date']):
					self.session_id_dictionary[session['date']] = []
				if not any(session['session_id'] in session_id for session_id in self.session_id_dictionary[session['date']]):
					if session['available_capacity'] > 0:
						logger.info(f'this particular session is not posted earlier {session["session_id"]} in {center["name"]}')
						if (center['fee_type'] == "Free"):
							res = {
								'name': center['name'],
								'block_name':center['block_name'],
								'vaccine_type':session['vaccine'] ,
								'fee': 'Free',
								'date':session['date'],
								'available_capacity': session['available_capacity'],
								'available_capacity_dose1': session['available_capacity_dose1'],
								'available_capacity_dose2': session['available_capacity_dose2']
							}
						else:
							res = {
								'name': center['name'],
								'block_name':center['block_name'],
								'vaccine_type':session['vaccine'] ,
								'fee': center['vaccine_fees']['fee'],
								'date':session['date'],
								'available_capacity': session['available_capacity'],
								'available_capacity_dose1': session['available_capacity_dose1'],
								'available_capacity_dose2': session['available_capacity_dose2']
							}
					else:
						res = {}
					if res.get('age_limit') == 18:
						output_18.append(res)
						self.session_id_dictionary[session['date']].append(session['session_id'])
					elif res.get('age_limit') == 45:
						output_45.append(res)
						self.session_id_dictionary[session['date']].append(session['session_id'])
		return output_18, output_45


	def parse_json_pincode(self, result):
		output = []
		sessions = result['sessions']
		if len(sessions)==0:
			return output
		for session in sessions:
			if session['available_capacity'] >= 0:
				res = { 'name': session['name'], 'block_name':session['block_name'], \
				'age_limit':session['min_age_limit'], 'vaccine_type':session['vaccine'] , \
				'date':session['date'],'available_capacity':session['available_capacity'] }
				if res['age_limit'] in self.age_limit:
					output.append(res)
		print(output)
		return output

	def call_api(self, url, headers, query_type, d1):
		response = requests.get(url, headers = headers)
		if response.status_code == 200:
			print("API call success")
			result = response.json()
			if query_type=='district_code':
				output_18, output_45 = self.parse_json_district_code(result)
			elif query_type =='pincode':
				output_18, output_45 = self.parse_json_pincode(result)
			else:
				print('incorrect query type\nquery type must be either district_code or pincode\n')
				return
			if len(output_18) > 0:
				logger.info(f'{output_18}')
				print("Vaccines available for age > 18")
				print('\007')
				result_str = ""
				for center in output_18:
					result_str = result_str + f"center['name'] ({center['date']})\n"
					result_str = result_str + f"Block: {center['block_name']}\n"
					result_str = result_str + f"Available vaccine: {center['available_capacity']} ({center['vaccine_type']})\n"
					result_str = result_str + f"(Dose 1: {center['available_vaccine_dose1']}, Dose 2: {center['available_vaccine_dose2']})\n"
					result_str = result_str + f"{center['vaccine_type']} ({center['fee']})\n"
					result_str = result_str + "Schedule: https://selfregistration.cowin.gov.in\n"
					result_str = result_str + "-----------------------------------------------------\n"
				#print(result_str)
				#self.send_email(result_str)
				self.send_telegram_msg_18(result_str)
			if len(output_45) > 0:
				logger.info(f'{output_45}')
				print("Vaccines available for age > 45")
				print('\007')
				result_str = ""
				for center in output_45:
					result_str = result_str + f"center['name'] ({center['date']})\n"
					result_str = result_str + f"Block: {center['block_name']}\n"
					result_str = result_str + f"Available vaccine: {center['available_capacity']} ({center['vaccine_type']})\n"
					result_str = result_str + f"(Dose 1: {center['available_vaccine_dose1']}, Dose 2: {center['available_vaccine_dose2']})\n"
					result_str = result_str + f"{center['vaccine_type']} ({center['fee']})\n"
					result_str = result_str + "Schedule: https://selfregistration.cowin.gov.in\n"
					result_str = result_str + "-----------------------------------------------------\n"
				#print(result_str)
				#self.send_email(result_str)
				self.send_telegram_msg_45(result_str)
			else:
				print(f"Vaccines not available for age limit {self.age_limit}\nTrying again\
				 after {self.time_delay} minute.....\n")
			if result != self.previous_result:
				logger.info('API Result changed')
			self.previous_result = result
		else:
			print("fsomething went wrong :(\nStatus code {response.status_code} \nTrying again......\
				after {self.time_delay} minute.....\n")


	def query(self, root_url, query_type, d1):
		print(ctime(time()))
		
		# format date
		__date = str(d1).replace("/","-")


		if query_type == 'district_code':
			url = root_url + "/calendarByDistrict?district_id=" + self.__district_code + "&date="+ __date

		elif query_type =='pincode':
			url = root_url + "/findByPin?pincode=" + self.__pincode + "&date=" + __date
		else:
			print('incorrect query type\nquery type must be either district_code or pincode\n')
			return
		self.call_api(url, self.headers, query_type, d1)


t = datetime.now()
if __name__ == '__main__':
	time_delay = 0.15
	query_type = 'district_code' # set it to "pincode" to query by pincode
	config_file_path = 'config.yml'
	
	print(f"querying by {query_type} .....")
	## root url and headers
	root_url = "https://cdn-api.co-vin.in/api/v2/appointment/sessions"
	
	vaccineSpotter = vaccineSpotter(config_file_path, time_delay)
	#vaccineSpotter.query(root_url, root_url, query_type)

	while True:
		delta = datetime.now()-t
		if delta.seconds >= time_delay * 60:
			#try:
			d1=datetime.strftime(datetime.today() + timedelta(days = 0), ("%d/%m/%Y"))
			print(f"trying to get slots for date:{d1}.....\n")
			vaccineSpotter.query(root_url, query_type, d1)
			t = datetime.now()
'''			except Exception as e:
				print(f"EXCEPTION: {e}")'''