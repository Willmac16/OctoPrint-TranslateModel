/*
 * View model for OctoPrint-TranslateModel
 *
 * Author: Will MacCormack
 * License: AGPLv3
 */
$(function() {
    function TranslatemodelViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.settingsViewModel = parameters[1];
        self.filesViewModel = parameters[2];
        self.access = parameters[3];

        self.xShift = ko.observable(0.0);
        self.yShift = ko.observable(0.0);
        self.translateFile = ko.observable();

        self.fileHide = /.translate_/;

        self.notifies = {};

        self.onUserLoggedIn = function () {
            self.updateFiles();
        }

        self.updateFiles = function() {
            if (self.loginState.hasPermission(self.access.permissions.FILES_LIST)) {
                console.log("Updating Files");
                var recursiveFileListing = function(entry) {
                    if (entry.type == "folder") {
                        _.each(entry.children, function(child) {
                            recursiveFileListing(child);
                        });
                    } else {
                        if (!entry.name.match(self.fileHide)) {
                            var file = $("<option></option>").text(entry.name).attr('value', entry.path);
                            $("#translate_table").append(file);
                        }
                    }
                };

                OctoPrint.files.list(true)
                .done(function(response) {
                    $("#translate_table").html("<option value=\"\" disabled selected>Select a File</option>");
                    _.each(response.files, function(entry) {
                        recursiveFileListing(entry);
                    });
                });
            } else {
                $("#translate_table").text("");
            }
        }

        self.translate = function() {
            if (self.translateFile()) {
                let index = self.translateFile() + parseFloat(self.xShift()).toFixed(3) + parseFloat(self.yShift()).toFixed(3);
                if (!(index in self.notifies)) {
                    $.ajax({
                        url: API_BASEURL + "plugin/translatemodel",
                        type: "POST",
                        dataType: "json",
                        data: JSON.stringify({
                            command: "translate",
                            x: parseFloat(self.xShift()).toFixed(3),
                            y: parseFloat(self.yShift()).toFixed(3),
                            file: self.translateFile()
                        }),
                        contentType: "application/json; charset=UTF-8"
                    });
                } else {
                    self.notifies[index].update({
                        title: 'Running Translating Model'});
                    console.log("File already translating");
                }
            } else {
                console.log("Select a file");
            }
        }

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin === "translatemodel") {
                if (data.state === "started") {
                    let index = data.file + data.x + data.y;
                    self.notifies[index] = new PNotify({
                        title: 'Started Translating Model',
                        type: 'info',
                        text: `Moving ${data.file} (${data.x}, ${data.y})`,
                        hide: false
                    });
                } else if (data.state === "running") {
                    let index = data.file + data.x + data.y;
                    if (index in self.notifies) {
                        self.notifies[index].update({
                            title: 'Running Translating Model'});
                    } else {
                        self.notifies[index] = new PNotify({
                            title: 'Running Translating Model',
                            type: 'info',
                            text: `Moving ${data.file} (${data.x}, ${data.y})`,
                            hide: false
                        });
                    }
                } else if (data.state === "finished") {
                    let index = data.file + data.x + data.y;
                    if (index in self.notifies) {
                        self.notifies[index].update({
                            title: 'Finished Translating Model',
                            text: `${data.file} moved <br/> (${data.x}, ${data.y}) <br/> is available @ ${data.path}`});
                        delete self.notifies['index'];
                    } else {
                        new PNotify({
                            title: 'Finished Translating Model',
                            type: 'info',
                            text: `${data.file} moved <br/> (${data.x}, ${data.y}) <br/> is available @ ${data.path}`,
                            hide: false
                        });
                    }

                } else if (data.state === "invalid") {
                    new PNotify({
                        title: 'Invalid Translate Model',
                        type: 'error',
                        text: `Cannot Translate non-gcode file: ${data.file}`,
                        hide: false
                    });
                }
            }
        }
    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: TranslatemodelViewModel,
        dependencies: [ "loginStateViewModel", "settingsViewModel", "filesViewModel", "accessViewModel" ],
        elements: [ "#tab_plugin_translatemodel" ]
    });
});
