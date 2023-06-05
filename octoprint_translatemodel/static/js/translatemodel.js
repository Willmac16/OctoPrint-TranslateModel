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
        self.gcodeViewModel = parameters[4];

        self.shifts = ko.observableArray([[0.0, 0.0]])
        self.xShift = ko.observable(0.0);
        self.yShift = ko.observable(0.0);
        self.translateFile = ko.observable("");
        self.afterTranslate = ko.observable("nothing");

        self.fileHide = /.translate_/;

        self.notifies = {};

        self.gcode_clone = false;

        self.filesViewModel.translateSelect = function (data) {
            // console.log("Translating file "+ data.path);
            self.translateFile(data.path);
        };

        $(document).ready(function() {
            let regex = /<div class="btn-group action-buttons"(?: data-bind="css: 'cpq-' \+ display\.split\('\.'\)\[1\]")?>([\s\S]*)<\/div>/mi;
			let template = '<div class="btn btn-mini" data-bind="click: function() { if ($root.loginState.isUser()) { $root.translateSelect($data) } else { return; } }, css: {disabled: !$root.loginState.isUser()}" href="#translate-model-modal" data-toggle="modal" title="Translate Model"><i class="fa fa-arrows-alt"></i></div>';

			$("#files_template_machinecode").text(function () {
                if($(this).text().indexOf('data-bind="css: \'cpq-\'') > 0) {
                    return $(this).text().replace(regex, '<div class="btn-group action-buttons" data-bind="css: \'cpq-\' + display.split(\'.\')[1]">$1	' + template + '></div>');
                } else {
                    return $(this).text().replace(regex, '<div class="btn-group action-buttons">$1	' + template + '></div>');
                }
			});
        });

        self.translate = function() {
            $.ajax({
                url: API_BASEURL + "plugin/translatemodel",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "translate",
                    shifts: self.shifts(),
                    file: self.translateFile(),
                    at: self.afterTranslate()
                }),
                contentType: "application/json; charset=UTF-8"
            });
        }

        self.preview = function() {
            if (self.gcodeViewModel) {
                console.log("Previewing translate");

                // translate preview api call
                $.ajax({
                    url: API_BASEURL + "plugin/translatemodel",
                    type: "POST",
                    dataType: "json",
                    data: JSON.stringify({
                        command: "preview",
                        shifts: self.shifts(),
                        file: self.translateFile()
                    }),
                    contentType: "application/json; charset=UTF-8"
                });
            }
        }

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin === "translatemodel") {
                if (data.state === "started") {
                    self.notifies[data.index] = new PNotify({
                        title: 'Started Translating Model',
                        type: 'info',
                        text: `Moving ${data.file}`,
                        hide: false
                    });
                } else if (data.state === "running") {
                    runnDict = {
                        title: 'Running Translating Model',
                        type: 'info',
                        text: `Moving ${data.file}`,
                        hide: false
                    }

                    if (data.index in self.notifies) {
                        self.notifies[data.index].update(runnDict);
                    } else {
                        self.notifies[data.index] = new PNotify(runnDict);
                    }
                } else if (data.state === "finished") {

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
                        text: `${data.file} moved <br/> took ${data.time.toFixed(2)}s ${lastText}`}

                    if (data.index in self.notifies) {
                        self.notifies[data.index].update(finishDict);
                        delete self.notifies[data.index];
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
                } else if (data.state === "preview") {
                    self.showGCodeViewer(data.previewGcode);
                }
            }
        }

        self.onDataUpdaterReconnect = function () {
            self.notifies = {};
        }

        self.addTranslation = function() {
            self.shifts.push([0.0, 0.0]);
        }

        self.removeTranslation = function() {
            self.shifts.remove(this);
        }

        // This is a function to trigger so that the enter key doesn't delete points
        self.safetyButton = function() {
            return
        }

        // GcodeViewer Stuff brought in for translate preview
        self.showGCodeViewer = function (response) {
            // load file preview into gcode viewer
            var par = {
                target: {
                    result: response
                }
            };

            GCODE.renderer.clear();
            GCODE.gCodeReader.loadFile(par);
            self.gcodeViewModel.renderer_centerViewport(true);


            const gcodeSquareSize = 530;

            // copy gcode viewer canvas object
            if (!self.gcode_clone) {
                self.gcode_clone = $('#gcode_canvas').clone();
                self.gcode_clone.attr('id', "TM-Preview-Canvas");
                self.gcode_clone.attr('width', gcodeSquareSize);
                self.gcode_clone.attr('height', gcodeSquareSize);
                self.gcode_clone.css('width', gcodeSquareSize);
                self.gcode_clone.css('height', gcodeSquareSize);


                $('#TM-GcodePreview').html(self.gcode_clone);
            }

            // copy canvas content once it loads
            if (self.preview_load_sub) self.preview_load_sub.dispose();
            self.preview_load_sub = self.gcodeViewModel.ui_modelInfo.subscribe(function(newValue) {
                var ctx = self.gcode_clone[0].getContext('2d');
                var original = $('#gcode_canvas')[0];

                // var imgData = original.getImageData(19, 19,
                //                                     519, 519);
                // ctx.putImageData(imgData, 0, 0, gcodeSquareSize, gcodeSquareSize);
                ctx.drawImage(original, 0, 0, 530, 530)
                self.preview_load_sub.dispose();
            });
        };
    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: TranslatemodelViewModel,
        dependencies: [ "loginStateViewModel", "settingsViewModel", "filesViewModel", "accessViewModel", "gcodeViewModel" ],
        optional: [ "gcodeViewModel" ],
        elements: [ "#settings_plugin_translatemodel" ]
    });
});
