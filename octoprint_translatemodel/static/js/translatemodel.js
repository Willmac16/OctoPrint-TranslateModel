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
                        var file = $("<option></option>").text(entry.name).attr('value', entry.path);
                        $("#translate_table").append(file);
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
                console.log(`Translating: ${self.translateFile()} (${self.xShift()},${self.yShift()})`);
                $.ajax({
                    url: API_BASEURL + "plugin/translatemodel",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        command: "translate",
                        x: self.xShift(),
                        y: self.yShift(),
                        file: self.translateFile()
                    }),
                    contentType: "application/json; charset=UTF-8"
                });
            } else {
                console.log("Select a file");
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
