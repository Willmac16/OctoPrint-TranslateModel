#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <regex>

#include <fstream>
#include <sstream>
#include <string>
#include <iostream>

// Logging Vars
static char module_name[] = "octoprint.plugins.translatemodel-C++";
static PyObject *logging_library = NULL;
static PyObject *logging_object= NULL;

// Thread State Var
// I use Py_UNBLOCK_THREADS and Py_BLOCK_THREADS instead of the begin/end pair
// so that the code can block threading only for logging and still compile
static PyThreadState *_save;

// logging wrappers
// self._logger.info
void info(std::string msg)
{
    Py_BLOCK_THREADS
    PyObject *logging_message = Py_BuildValue("s", msg.c_str());
    Py_XINCREF(logging_message);
    PyObject_CallMethod(logging_object, "info", "O", logging_message, NULL);

    Py_DECREF(logging_message);
    Py_UNBLOCK_THREADS
}

// self._logger.debug
void debug(std::string msg)
{
    Py_BLOCK_THREADS
    PyObject *logging_message = Py_BuildValue("s", msg.c_str());
    Py_XINCREF(logging_message);
    PyObject_CallMethod(logging_object, "debug", "O", logging_message, NULL);

    Py_DECREF(logging_message);
    Py_UNBLOCK_THREADS
}

float roundTo(int percision, float in)
{
    float out;
    for (int i = 0; i < percision; i++)
    {
        in *= 10;
    }

    out = round(in);
    for (int i = 0; i < percision; i++)
    {
        out /= 10;
    }
    return out;
}

float parseFloat(std::istream *stream)
{
    int n;
    bool point = false, negative = false;

    std::string val = "";
    while ((n = stream->peek()))
    {
        if (n > 47 && n <= 57)
        {
            val += stream->get();
        }
        else if (n == 46)
        {
            if (!point)
            {
                val += stream->get();
                point = true;
            }
            else
                break;
        }
        else if (n == '-')
        {
            if (!negative)
            {
                val += stream->get();
                negative = true;
            }
            else
                break;
        }
        else
            break;
    }

    if (val != "")
        return std::stof(val);
    else
        return NAN;
}

void translateLine(double *shift, std::string line, std::ostream *out, bool *absolute, std::string *lineEnd)
{
    std::istringstream iss(line);
    char cmd;
    int num;
    if ((iss >> cmd) && toupper(cmd) == 'G')
    {
        if ((iss >> num))
        {
            if (num >= 0 && num < 4)
            {
                *out << "G" << num;
                char arg;
                while ((iss >> arg) && arg != ';')
                {
                    if (arg == '(')
                    {
                        *out << arg;
                        // std::cout << arg;
                        do
                        {
                            iss >> arg;
                            *out << arg;
                            // std::cout << arg;
                        }
                        while (arg != ')');
                    }
                    char upp = toupper(arg);
                    switch (upp)
                    {
                        case 'X':
                            if (*absolute)
                                *out << " " << arg << roundTo(3, (parseFloat(&iss)+shift[0]));
                            else
                                *out << " " << arg;
                            break;
                        case 'Y':
                            if (*absolute)
                                *out << " " << arg << roundTo(3, (parseFloat(&iss)+shift[1]));
                            else
                                *out << " " << arg;
                            break;
                        default:
                            if (upp > 'A' && upp <= 'Z')
                            {
                                *out << " " << arg;
                            }
                            else
                            {
                                *out << arg;
                            }
                            break;
                    }
                }

                std::string comment;
                std::getline(iss, comment);

                if (comment != "")
                {
                    *out << " ; " << comment;
                }
            }
            else if (num == 91)
            {
                *absolute = false;
                *out << line;
            }
            else if (num == 90)
            {
                *absolute = true;
                *out << line;
            }
            else
            {
                *out << line;
            }
        }
    }
    else
    {
        *out << line;
    }
    *out << *lineEnd;
}

std::string translate(double shifts[][2], int numShifts, std::string inPath,
                        std::string startRegex, std::string stopRegex, std::string version, int preview)
{
    std::ifstream infile(inPath);
    std::ostream out(NULL);

    // only used if translating normally
    std::string opath;
    std::filebuf fileBuffer;
    // only used if previewing
    std::ostringstream previewGcode;


    if (preview)
    {
        out.rdbuf(previewGcode.rdbuf());

        // Translate first 10 layers in case of multilayer wipe like MMU2
        preview = 10;
    }
    else
    {
        std::ostringstream op;
        std::ostringstream outPath;

        op << ".translate_" << numShifts << "_shifts" << ".gcode";
        std::regex r("\\.g(co)*(de)*");
        outPath << std::regex_replace(inPath, r, op.str());


        opath = outPath.str();
        info("Working on file " + opath);

        fileBuffer.open(opath.c_str(), std::ios_base::out);

        out.rdbuf(&fileBuffer);
    }

    std::string line;

    std::regex start(startRegex);
    std::regex end(stopRegex);

    std::regex m555("^M555.*$");    //NEW PATTERN FOR PRUSA M555 "bed area to probe" COMMAND

    bool absolute = true;

    int afterStart = -1;

    std::string lineEnd = "\n";

    std::ostringstream layerStream;


    getline(infile, line);

    if (!line.empty() && line[line.size()-1] == '\r')
    {
        lineEnd = "\r\n";
    }

    out << "; Processed by OctoPrint-TranslateModel " << version << lineEnd << lineEnd;

    do
    {
        // Remove \r if file was CTLF
        if (!line.empty() && line[line.size()-1] == '\r')
        {
            line.erase(line.size()-1);
        }

        if (afterStart != 1)
        {
            if (std::regex_match(line, m555)) // THIS BLOCK IS FOR PRUSA M555, WHICH DEFINES "USED BED AREA" FOR G29 PROBING
            {
                // NEW CODE HERE FOR M555 AS FOLLOWS:
                //   - Decode existing line for original M555 X, Y, W, H values
                std::istringstream iss(line);
                char arg;
                float origX = 0;
                float origY = 0;
                float origW = 0;
                float origH = 0;
                while (iss >> arg)
                {
                    char upp = toupper(arg);
                    // if (iss >> num)
                    switch (upp)
                    {
                    case 'M':
                            break;
                    case 'X':
                            origX = parseFloat(&iss);
                            break;
                    case 'Y':
                            origY = parseFloat(&iss);
                            break;
                    case 'W':
                            origW = parseFloat(&iss);
                            break;
                    case 'H':
                            origH = parseFloat(&iss);
                            break;
                    }
                }
                //  - If multiple shifts:
                //      - iterate to find minimum and maximum X translation "minXoffset" and "maxXoffset"
                //      - iterate to find minimum and maximum Y translation "minYoffset" and "maxYoffset"
                //      - set minX = origX+minXoffset  (new x origin of entire print, all shifts/copies)
                //		- set minY = origY+minYoffset  (new y origin of entire print, all shifts/copies)
                //    else
                //	    - set minX=maxX=origX+shift, minY=maxY=origY+shift  (new origin is minX, minY)

                float minX;
                float minY;
                float maxX;
                float maxY;

                if (numShifts > 1) // multiple shifts, find extents of build plate content
                {
                    float minXshift;
                    float maxXshift;
                    float minYshift;
                    float maxYshift;

                    for (int i = 0; i < numShifts; i++)
                    {
                            double *shift = shifts[i];
                            if (i == 0)
                            {
                                minXshift = shift[0];
                                maxXshift = shift[0];
                                minYshift = shift[1];
                                maxYshift = shift[1];
                            }
                            else
                            {
                                if (shift[0] < minXshift)
                                    minXshift = shift[0];
                                if (shift[0] > maxXshift)
                                    maxXshift = shift[0];
                                if (shift[1] < minYshift)
                                    minYshift = shift[1];
                                if (shift[1] > maxYshift)
                                    maxYshift = shift[1];
                            }
                    }
                    minX = origX + minXshift;
                    minY = origY + minYshift;
                    maxX = origX + maxXshift;
                    maxY = origY + maxYshift;
                }
                else // only one shift
                {
                    minX = origX + shifts[0][0];
                    maxX = minX;
                    minY = origY + shifts[0][1];
                    maxY = minY;
                }
                //  - Calculate newW = (maxX+W)-minX
                //  - Calculate newH = (maxY+H)-minY
                float newW;
                float newH;
                newW = maxX + origW - minX;
                newH = maxY + origH - minY;
                //  - Write new M555 X<minX> Y<minY> W<newW> H<newH>
                out << "M555 X" << roundTo(3, minX) << " Y" << roundTo(3, minY) << " W" << roundTo(3, newW) << " H" << roundTo(3, newH) << " ;TRANSLATE-MODEL_BED_AREA" << lineEnd;
            }
            else if (std::regex_match(line, start))
            {
                afterStart = true;
                out << line << lineEnd << ";TRANSLATE-MODEL_LAYER_START" << lineEnd;
                layerStream = std::ostringstream();
            }
            else
            {
                out << line << lineEnd;
            }
        }
        else
        {
            if (std::regex_match(line, end))
            {
                // spit out copies up until now
                if (numShifts > 1)
                {
                    // process the layer one shift copy at a time

                    // any state variable (e.g. absolute positioning) need to be copied out for each shift copy
                    // then saved at the end
                    bool *abs = new bool(false);

                    std::istringstream layerIStream = std::istringstream(layerStream.str());
                    for (int i = 0; i < numShifts; i++)
                    {
                        *abs = absolute;
                        double *shift = shifts[i];

                        while (getline(layerIStream, line))
                        {
                            translateLine(shift, line, &out, abs, &lineEnd);
                        }

                        layerIStream.clear();
                        layerIStream.seekg(0);
                    }

                    absolute = *abs;
                    delete abs;
                }

                afterStart = false;
                out << line << lineEnd << ";TRANSLATE-MODEL_STOP" << lineEnd;
                layerStream = std::ostringstream();
            }
            else if (std::regex_match(line, start))
            {
                if (numShifts > 1)
                {
                    // process the layer one shift copy at a time

                    // any state variable (e.g. absolute positioning) need to be copied out for each shift copy
                    // then saved at the end
                    bool *abs = new bool(false);

                    std::istringstream layerIStream = std::istringstream(layerStream.str());
                    for (int i = 0; i < numShifts; i++)
                    {
                        *abs = absolute;
                        double *shift = shifts[i];

                        while (getline(layerIStream, line))
                        {
                            translateLine(shift, line, &out, abs, &lineEnd);
                        }

                        layerIStream.clear();
                        layerIStream.seekg(0);
                    }

                    absolute = *abs;
                    delete abs;
                }

                // exit out if we are previewing so we only process one layer
                if (preview)
                {
                    if (preview == 1)
                        return previewGcode.str();
                    else
                        preview--;
                }

                out << line << lineEnd << ";TRANSLATE-MODEL_LAYER_START" << lineEnd;
                layerStream = std::ostringstream();
            }
            else
            {
                // if we only have one shift then process as we scan the file
                // but if we have more than one, we dump the line into the layerStream object
                if (numShifts > 1)
                {
                    layerStream << line << lineEnd;
                }
                else
                {
                    translateLine(shifts[0], line, &out, &absolute, &lineEnd);
                }
            }
        }
    }
    while (getline(infile, line));

    if (preview)
    {
        return previewGcode.str();
    }
    else
    {
        // spit out copies for any left over lines
        if (numShifts > 1)
        {
            // process the layer one shift copy at a time

            // any state variable (e.g. absolute positioning) need to be copied out for each shift copy
            // then saved at the end
            bool *abs = new bool(false);

            std::istringstream layerIStream = std::istringstream(layerStream.str());
            for (int i = 0; i < numShifts; i++)
            {
                *abs = absolute;
                double *shift = shifts[i];

                while (getline(layerIStream, line))
                {
                    translateLine(shift, line, &out, abs, &lineEnd);
                }

                layerIStream.clear();
                layerIStream.seekg(0);
            }

            absolute = *abs;
            delete abs;
        }

        return opath;
    }
}

static PyObject *
translate_translate(PyObject *self, PyObject *args)
{
    PyObject *shiftList;

    const char *path, *sr, *er, *ver;

    int preview = false;

    PyObject *logging_message = Py_BuildValue("s", "Before tuple parse");
    Py_XINCREF(logging_message);
    PyObject_CallMethod(logging_object, "debug", "O", logging_message, NULL);
    Py_DECREF(logging_message);

    // ADD THE 2 PARENTHESIS AFTER FINAL VAR (THIS HAS HAPPENED TWICE NOW)
    if (!PyArg_ParseTuple(args, "Os(ss)s|p", &shiftList, &path,
                                            &sr, &er,
                                            &ver, &preview))
        return NULL;
    Py_INCREF(shiftList);

    logging_message = Py_BuildValue("s", "After tuple parse");
    Py_XINCREF(logging_message);
    PyObject_CallMethod(logging_object, "debug", "O", logging_message, NULL);
    Py_DECREF(logging_message);

    // parse through all the shifts
    shiftList = PySequence_Fast(shiftList, "argument must be iterable");
    if(!shiftList)
        return 0;

    const int numShifts = PySequence_Fast_GET_SIZE(shiftList);
    double shifts[numShifts][2];

    for (int i = 0; i < numShifts; i++)
    {
        PyObject *shiftSet = PySequence_Fast_GET_ITEM(shiftList, i);
        shiftSet = PySequence_Fast(shiftSet, "argument must be iterable");

        // Get the x then y coord and convert to pyfloat then c double
        for (int j = 0; j < 2; j++)
        {
            shifts[i][j] = PyFloat_AS_DOUBLE(PyNumber_Float(PySequence_Fast_GET_ITEM(shiftSet, j)));
        }
    }

    // for (int i = 0; i < numShifts; i++)
    // {
    //     std::cout << shifts[i][0] << ", " << shifts[i][1] << std::endl;
    // }

    std::string opath;

    Py_DECREF(shiftList);

    Py_UNBLOCK_THREADS
    debug("Started translating");

    // opath is output path if regular, but is actually the gcode preview for preview mode
    opath = translate(shifts, numShifts, (std::string) path,
                        (std::string) sr, (std::string) er, (std::string) ver, preview);
    debug("Done translating");
    Py_BLOCK_THREADS
    return Py_BuildValue("s", opath.c_str());
}

static PyObject *
translate_test(PyObject *self, PyObject *args)
{
    Py_UNBLOCK_THREADS
    char *msg;

    if (!PyArg_ParseTuple(args, "s", &msg))
    {
        return NULL;
    }

    std::string out = "Hello ";

    out += msg;


    debug(out);

    Py_BLOCK_THREADS
    Py_RETURN_NONE;
}

static PyObject *
translate_preview_test(PyObject *self, PyObject *args)
{
    int num, boo = false;

    if (!PyArg_ParseTuple(args, "i|p", &num, &boo))
    {
        return NULL;
    }

    std::cout << num << std::endl;

    if (boo)
        std::cout << "True" << std::endl;
    else
        std::cout << "False" << std::endl;

    Py_RETURN_NONE;
}

static PyMethodDef TranslateMethods[] = {
    {"translate",  translate_translate, METH_VARARGS,
     "Translate a gcode file"},
    {"test",  translate_test, METH_VARARGS,
    "Just a test method"},
    {"preview_test",  translate_preview_test, METH_VARARGS,
    "Test of preview var passing"},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static struct PyModuleDef translatemodule = {
    PyModuleDef_HEAD_INIT,
    "translate",   /* name of module */
    NULL, /* module documentation, may be NULL */
    -1,       /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    TranslateMethods
};

PyMODINIT_FUNC
PyInit_translate(void)
{
    logging_library = PyImport_ImportModuleNoBlock("logging");
    logging_object = PyObject_CallMethod(logging_library, "getLogger", "O", Py_BuildValue("s", module_name));
    Py_XINCREF(logging_object);

    return PyModule_Create(&translatemodule);
}
