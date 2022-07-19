import sys
import subprocess
import json
from pebble import concurrent
import io
import os
import matlab.engine
import tempfile
sys.path.append("../..")

import earley_parser as parser

f = open('../../../antlr4/config.json')
data = json.load(f)
antlr_programs = data['antlr_programs']
f.close()
eng = matlab.engine.connect_matlab()
exec_map = {}

def save_file(string, dir):
	"""
	Save a file to the given directory.
	"""
	with tempfile.NamedTemporaryFile(suffix='.mdl', dir=dir, delete=False) as fi:
		fi.write(bytes(string, 'utf-8'))
		fi.flush()
		return fi.name

def check(s, p, label=None):
	if s in exec_map: 
		# Input already tested
		return exec_map[s]
	if p in antlr_programs: v =  _check_antlr(s, p) 
	elif p == 'simulink':
		mat = matlab.engine.find_matlab()
		if len(mat)==0:
			global eng
			eng = matlab.engine.connect_matlab()
		future = _check_simulink(s)
		try:
			v=future.result()
		except TimeoutError:
			save_file(s, 'Simulink/timeout')
			return False
		except Exception as e:
			print("Error: "+str(e))
			save_file(s, 'Simulink/timeout')
			return False
		
	
	else: v =  _check(s, p)
	exec_map[s] = v
	return v

@concurrent.process(timeout=30)
def _check_simulink(string):
	global eng
	f_name = save_file(string, 'Simulink/Tmp/')
	# case 1: compiles and uncompiles fine
	# case 2: doesn't uncompile
	# case 3: doesn't compile
	try:
		
		out = io.StringIO()
		eng.load_system(f_name, stdout=out)
		if 'Warning' in out.getvalue():
			raise Exception('Warning')
		model = eng.bdroot()
		try:
			eng.slreportgen.utils.compileModel(model, nargout = 0, stdout=out)
			# print(f"compiled {f_name}: {date.now()}".ljust(80), end='')
			try:
				eng.slreportgen.utils.uncompileModel(model, nargout = 0, stdout=out)
			except:
				# print(f"doesn't uncompile {date.now()}".ljust(50), end='\r')
				save_file(string, 'Simulink/Crash/uncompile')
				
				return False
		except:
			# print(f"doesn't compile {date.now()}".ljust(50), end='\r')
			mat = matlab.engine.find_matlab()
			if len(mat)==0:
				save_file(string, 'Simulink/Crash/compiletime')
				
			return False
		try:
			eng.close_system(f_name, nargout = 0)
			# print(f"closed {date.now()}".ljust(50), end='\r')
		except:
			# print(f"doesn't close {date.now()}".ljust(50), end='\r')
			save_file(string, 'Simulink/Crash/close')
			return True

		# print(f"compile and close {date.now()}".ljust(50), end='\r')
		return True
	except Exception as e:
		# print(f"doesn't load {date.now()}".ljust(50), end='\r')
		# print(e)
		return False

	finally:
		try:
			if os.path.exists(f_name):
				os.remove(f_name)
		except:
			pass

def _check(s, p):
	try:
		parser.check(s, p)
		# Valid input
		return True

	except Exception as e:
		# Invalid input
		return False

def _check_antlr(s, p):
	try:
		file1 = open('input', 'w')
		file1.write(s)
		file1.close()
		result = subprocess.check_output(get_command(p), shell=True, stderr=subprocess.STDOUT, timeout=10)
		output = result.decode('utf-8')
		if output == '': 
			return True
		else:
			return False
	except Exception as e:
		print("Error: "+str(e))
		return False

def get_command(p):
	cmd = 'python3 ../../../antlr4/' + p + '/parse.py input'
	return cmd
