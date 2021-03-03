# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.filemanager import FileDestinations
from octoprint.access.permissions import Permissions

from octoprint.events import Events

import translate

import re, threading, time

# Worker to translate models in a seperate thread
class TranslateWorker(threading.Thread):
	def __init__(self, _plugin, x, y, file, after_translate):
		threading.Thread.__init__(self)
		self._plugin = _plugin
		self.x = x
		self.y = y
		self.file = file
		self.after_translate = after_translate

	def run(self):
		# Let the log+frontend know that the file is being processed
		self._plugin._logger.info("translate called, {}: ({}, {})".format(self.file, self.x, self.y))
		self._plugin._plugin_manager.send_plugin_message("translatemodel", dict(state='started', file=self.file, x=self.x, y=self.y))

		origPath = self._plugin._file_manager.path_on_disk(FileDestinations.LOCAL, self.file)

		startTime = time.time()
		# runs the c++ file processing
		regexTuple = ("^; printing object !(ENDGCODE)", "^; stop printing object !(ENDGCODE)",
						"^;(( BEGIN_|AFTER_)*LAYER_(CHANGE|OBJECT)|LAYER:[0-9]+| [<]*layer [0-9]+[>,]*)", "end")
		longPath = translate.translate(float(self.x), float(self.y), origPath, regexTuple)

		endTime = time.time()
		procTime = endTime-startTime


		# work out the different forms of the path
		shortPath = self._plugin._file_manager.path_in_storage(FileDestinations.LOCAL, longPath)
		path, name = self._plugin._file_manager.canonicalize(FileDestinations.LOCAL, longPath)

		# takes the file from c++ and adds it into octoprint
		newFO = octoprint.filemanager.util.DiskFileWrapper(name, longPath, move=True)
		self._plugin._file_manager.add_file(FileDestinations.LOCAL, longPath, newFO, allow_overwrite=True)

		# Let the log+frontend know that the file is done
		self._plugin._logger.info("Done with file {}: ({}, {}) took {}s; saved as {}".format(self.file, self.x, self.y, procTime, shortPath))
		self._plugin._plugin_manager.send_plugin_message("translatemodel", dict(state='finished', file=self.file, x=self.x, y=self.y, time=procTime, path=shortPath, afterTranslate=self.after_translate))

		index = self.file + self.x + self.y
		self._plugin.translating.remove(index)

		# load and print the file as necessary
		if self.after_translate in ("load", "print", "printAndDelete"):
			print = self.after_translate in ("print", "printAndDelete")
			self._plugin._printer.select_file(shortPath, False, printAfterSelect=print)
			self._plugin.delete_files.append(shortPath)


class TranslatemodelPlugin(octoprint.plugin.SettingsPlugin,
                           octoprint.plugin.AssetPlugin,
                           octoprint.plugin.TemplatePlugin,
						   octoprint.plugin.SimpleApiPlugin,
						   octoprint.plugin.StartupPlugin,
						   octoprint.plugin.EventHandlerPlugin):

	translating = []
	delete_files = []


	##~~ StartupPlugin mixin

	def on_after_startup(self):
		self._logger.debug("ON AFTER STARTUP")
		translate.test("ON AFTER STARTUP")

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
			js=["js/translatemodel.js"]
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
			translate=["file", 'x', 'y', 'at'],
			test=[]
		)

	def on_api_command(self, command, data):
		if command == "test":
			self._logger.info("test called")
		elif command == "translate":
			# TODO: handle double translating (i.e. translating a translated file) better
			if Permissions.FILES_UPLOAD.can() and octoprint.filemanager.valid_file_type(data['file'], type="gcode"):
				index = data['file'] + data['x'] + data['y']

				if (index not in self.translating):
					self.translating.append(index)
					worker = TranslateWorker(self, data['x'], data['y'], data['file'], data['at'])
					worker.start()
				else:
					self._plugin_manager.send_plugin_message("translatemodel", dict(state='running', file=data['file'], x=data['x'], y=data['y']))

			else:
				self._plugin_manager.send_plugin_message("translatemodel", dict(state='invalid', file=data['file']))


	##~~EventHandlerPlugin mixin

	def on_event(self, event, payload):
		if event in ("PrintFailed", "PrintDone", "PrintCanceled") and payload['origin'] == "local":
			if payload['path'] in self.delete_files:
				self._logger.info("Deleting {} after print end".format(payload['path']))
				self._file_manager.remove_file(FileDestinations.LOCAL, payload['path'])
				self.delete_files.remove(payload['path'])
				self._printer.unselect_file()
		elif event == "FileSelected" and payload['origin'] == "local":
			self._plugin_manager.send_plugin_message("translatemodel", dict(state='selected', file=payload['path']))



__plugin_name__ = "Translate Model Plugin"

__plugin_pythoncompat__ = ">=3,<4" # python 2 and 3

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = TranslatemodelPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
