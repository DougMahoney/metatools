from shared.tools.thread import getThreadState, Thread

from datetime import datetime #, timedelta



class SysHijack(object):
	"""Capture a thread's system state and redirect it's standard I/O."""

	__slots__ = ('_thread_state', 
				 '_target_thread', 
				 '_io_proxy',
	             
	             '_original_stdin', 
	             '_original_stdout', 
	             '_original_stderr', 
	             '_original_displayhook',
	             )
	
	# _FAILSAFE_TIMEOUT = 20
	
	def __init__(self, thread):
		
		self._target_thread = thread
		
		self._io_proxy = ProxyIO(coupled_sys=self)
		
		self._init_time = datetime.now()
		
		self._original_stdin       = self._thread_sys.stdin
		self._original_stdout      = self._thread_sys.stdout
		self._original_stderr      = self._thread_sys.stderr
		self._original_displayhook = self._thread_sys.displayhook
				
		self._install()
		
		# @async(self._FAILSAFE_TIMEOUT)
		# def failsafe_uninstall(self=self):
		# 	self._restore()
		# failsafe_uninstall()
		
	def _install(self):
		"""Redirect all I/O to proxy's endpoints"""
		self._thread_sys.stdin       = self._io_proxy.stdin
		self._thread_sys.stdout      = self._io_proxy.stdout
		self._thread_sys.stderr      = self._io_proxy.stderr
		self._thread_sys.displayhook = self._io_proxy.displayhook
			
	def _restore(self):
		"""Restore all I/O to original's endpoints"""
		self._thread_sys.stdin       = self._original_stdin
		self._thread_sys.stdout      = self._original_stdout
		self._thread_sys.stderr      = self._original_stderr
		self._thread_sys.displayhook = self._original_displayhook
		

	@property
	def _thread_state(self):
		return getThreadState(self._target_thread)
	
	@property
	def _thread_sys(self):
		return self._thread_state.systemState
	

	@property
	def stdin(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.stdin
		else:
			return self._original_stdin

	@property
	def stdout(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.stdout
		else:
			return self._original_stdout
			
	@property
	def stderr(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.stderr
		else:
			return self._original_stderr
			
	@property
	def displayhook(self):
		if Thread.currentThread() is self._target_thread:
			return self._io_proxy.displayhook
		else:
			return self._original_displayhook
			

	def _getframe(self, depth=0):
		#print >>self.stdout, '[~] getting frame %d' % depth
		frame = self._thread_state.frame
		while depth > 0 and frame:
			depth -= 1
			frame = frame.f_back
		return frame


	def settrace(self, tracefunc=None):
		self._thread_sys.settrace(tracefunc)


	def setprofile(self, profilefunc=None):
		if profilefunc is None:
			self._thread_sys.setprofile(None)
		else:
			self._thread_sys.setprofile(profilefunc)


	def __del__(self):
		self._restore()
	

	# Override masking mechanic (the hijack)
	
	def __getattr__(self, attribute):
		"""Get from this class first, otherwise use the wrapped item."""
		try:
			return super(SysHijack, self).__getattr__(attribute)
		except AttributeError:
			return getattr(self._thread_sys).__getattr__(attribute)
	
	
	def __setattr__(self, attribute, value):
		"""Set to this class first, otherwise use the wrapped item."""
		try:
			super(SysHijack, self).__setattr__(attribute, value)
		except AttributeError:
			setattr(self._thread_sys, attribute, value)
