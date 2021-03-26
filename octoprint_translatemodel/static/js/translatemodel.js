/*
 * View model for OctoPrint-TranslateModel
 *
 * Author: Will MacCormack
 * License: AGPLv3
 */
function roundTo(digits, number) {
    for (let i=0; i<digits; i++) {
        number *= 10;
    }
    out = Math.round(number)
    for (let i=0; i<digits; i++) {
        out /= 10;
    }
    return out;
}

$(function() {
    function TranslatemodelViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.settingsViewModel = parameters[1];
        self.filesViewModel = parameters[2];
        self.access = parameters[3];

        self.xShift = ko.observable(0.0);
        self.yShift = ko.observable(0.0);
        self.translateFile = ko.observable("");
        self.afterTranslate = ko.observable("nothing");

        self.fileHide = /.translate_/;

        self.notifies = {};

        self.filesViewModel.translateSelect = function (data) {
            // console.log("Translating file "+ data.path);
            self.translateFile(data.path);
        };

        $(document).ready(function() {
            let regex = /<div class="btn-group action-buttons">([\s\S]*)<.div>/mi;
            let template = '<div class="btn btn-mini" data-bind="click: function() { if ($root.loginState.isUser()) { $root.translateSelect($data) } else { return; } }, css: {disabled: !$root.loginState.isUser()}" href="#translate-model-modal" data-toggle="modal" title="Translate Model"><i class="fa fa-arrows-alt"></i></div>';

            $("#files_template_machinecode").text(function () {
                return $(this).text().replace(regex, '<div class="btn-group action-buttons">$1	' + template + '></div>');
            });
        });

        self.translate = function() {
            if (self.translateFile() != "") {
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
                            file: self.translateFile(),
                            at: self.afterTranslate()
                        }),
                        contentType: "application/json; charset=UTF-8"
                    });
                } else {
                    self.notifies[index].update({
                        title: 'Running Translating Model'});
                    console.log("File already translating");
                }
            } else {
                console.log("select a file");
            }
        }

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin === "translatemodel") {
                if (data.state === "selected") {
                    self.translateFile(data.file)
                } else if (data.state === "started") {
                    let index = data.file + data.x + data.y;
                    self.notifies[index] = new PNotify({
                        title: 'Started Translating Model',
                        type: 'info',
                        text: `Moving ${data.file} (${data.x}, ${data.y})`,
                        hide: false
                    });
                } else if (data.state === "running") {
                    let index = data.file + data.x + data.y;
                    runnDict = {
                        title: 'Running Translating Model',
                        type: 'info',
                        text: `Moving ${data.file} (${data.x}, ${data.y})`,
                        hide: false
                    }

                    if (index in self.notifies) {
                        self.notifies[index].update(runnDict);
                    } else {
                        self.notifies[index] = new PNotify(runnDict);
                    }
                } else if (data.state === "finished") {
                    let index = data.file + data.x + data.y;

                    let lastText = "<br> ";
                    if (data.afterTranslate === "load")
                        lastText += `is loaded and ready to print`;
                    else if (data.afterTranslate === "print")
                        lastText += `is printing`;
                    else if (data.afterTranslate === "printAndDelete")
                        lastText += `is printing and will delete once complete`;
                    else
                        lastText += `is available @ ${data.path}`;

                    finishDict = {
                        type: 'success',
                        title: 'Finished Translating Model',
                        text: `${data.file} moved <br/> (${data.x}, ${data.y}) <br/> took ${roundTo(2, data.time)}s ${lastText}`}

                    if (index in self.notifies) {
                        self.notifies[index].update(finishDict);
                        delete self.notifies[index];
                    } else {
                        new PNotify(finishDict);
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

        self.onDataUpdaterReconnect = function () {
            self.notifies = {};
        }
    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: TranslatemodelViewModel,
        dependencies: [ "loginStateViewModel", "settingsViewModel", "filesViewModel", "accessViewModel" ],
        elements: [ "#settings_plugin_translatemodel" ]
    });
});
