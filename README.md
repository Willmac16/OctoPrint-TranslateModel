# OctoPrint-TranslateModel

Translate Model allows you to move models around in gcode files without reslicing.

## Features
* Select files via the translate button in the file pane
* Quick and easy model movement along the x and y axes
* Options to automatically print files after translation

<img width="137" alt="translateActionButton" src="https://user-images.githubusercontent.com/27445690/109603898-74bc8000-7ad7-11eb-8e1c-2fc39e207aa2.png">
<img width="620" alt="translateTab" src="https://user-images.githubusercontent.com/27445690/109603901-75551680-7ad7-11eb-8f70-653ae53117b1.png">
<img alt="viewerGraphic" src="https://user-images.githubusercontent.com/27445690/109603903-75edad00-7ad7-11eb-97c9-5fcb1c18bc38.png">


## Setup

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/master/bundledplugins/pluginmanager.html)
or manually using this URL:

    https://github.com/Willmac16/OctoPrint-TranslateModel/archive/main.zip

* This plugin will compile its C++ code on install, but this should be pretty quick.

## Credits

* Thanks to KenLucke for the plugin suggestion and testing help.
* Thanks to AlexDashwood for the fix for a conflict with ContinuousPrint
* Thanks to ScottWell1 for adding support for Prusa's `M555` command
* Thanks to jacopotediosi for XSS Vulnerability Fixes
