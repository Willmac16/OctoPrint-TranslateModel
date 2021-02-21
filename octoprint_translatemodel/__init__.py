# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.filemanager import FileDestinations

import translate

import re, threading

class TranslateWorker(threading.Thread):
	def __init__(self, _file_manager, _logger, _plugin_manager, x, y, file):
		threading.Thread.__init__(self)
		self._file_manager = _file_manager
		self._logger = _logger
		self._plugin_manager = _plugin_manager
		self.x = x
		self.y = y
		self.file = file
	def run(self):
		self._logger.info("translate called, {}: ({}, {})".format(self.file, self.x, self.y))
		self._plugin_manager.send_plugin_message("translatemodel", dict(state='started', file=self.file, x=self.x, y=self.y))

		origPath = self._file_manager.path_on_disk(FileDestinations.LOCAL, self.file)

		longPath = translate.translate(self.x, self.y, origPath)
		shortPath = self._file_manager.path_in_storage(FileDestinations.LOCAL, longPath)
		path, name = self._file_manager.canonicalize(FileDestinations.LOCAL, longPath)

		newFO = octoprint.filemanager.util.DiskFileWrapper(name, longPath, move=True)
		self._file_manager.add_file(FileDestinations.LOCAL, longPath, newFO, allow_overwrite=True)
		self._logger.info("Done with file {}: ({}, {}); saved as {}".format(self.file, self.x, self.y, longPath))
		self._plugin_manager.send_plugin_message("translatemodel", dict(state='finished', file=self.file, x=self.x, y=self.y, path=shortPath))



class TranslatemodelPlugin(octoprint.plugin.SettingsPlugin,
                           octoprint.plugin.AssetPlugin,
                           octoprint.plugin.TemplatePlugin,
						   octoprint.plugin.SimpleApiPlugin):

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			# put your plugin's default settings here
		)

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/translatemodel.js"],
			css=["css/translatemodel.css"],
			less=["less/translatemodel.less"]
		)

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
		# for details.
		return dict(
			translatemodel=dict(
				displayName="Translate Model Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="Willmac16",
				repo="OctoPrint-TranslateModel",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/Willmac16/OctoPrint-TranslateModel/archive/{target_version}.zip"
			)
		)


	##~~ SimpleAPIPlugin mixin

	def get_api_commands(self):
		return dict(
			translate=["file", 'x', 'y'],
			test=[]
		)

	def on_api_command(self, command, data):
		if command == "test":
			self._logger.info("test called".format())
		elif command == "translate":
			x = round(float(data['x']), 3)
			y = round(float(data['y']), 3)
			worker = TranslateWorker(self._file_manager, self._logger, self._plugin_manager, x, y, data['file'])
			worker.start()


__plugin_name__ = "Translate Model Plugin"

__plugin_pythoncompat__ = ">=2.7,<4" # python 2 and 3

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = TranslatemodelPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
