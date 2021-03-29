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

void translateLine(double *shift, std::string line, std::ofstream *outfile, bool *absolute, std::string *lineEnd)
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
                *outfile << "G" << num;
                char arg;
                while ((iss >> arg) && arg != ';')
                {
                    if (arg == '(')
                    {
                        *outfile << arg;
                        // std::cout << arg;
                        do
                        {
                            iss >> arg;
                            *outfile << arg;
                            // std::cout << arg;
                        }
                        while (arg != ')');
                    }
                    char upp = toupper(arg);
                    switch (upp)
                    {
                        case 'X':
                            if (*absolute)
                                *outfile << " " << arg << roundTo(3, (parseFloat(&iss)+shift[0]));
                            else
                                *outfile << " " << arg;
                            break;
                        case 'Y':
                            if (*absolute)
                                *outfile << " " << arg << roundTo(3, (parseFloat(&iss)+shift[1]));
                            else
                                *outfile << " " << arg;
                            break;
                        default:
                            if (upp > 'A' && upp <= 'Z')
                            {
                                *outfile << " " << arg;
                            }
                            else
                            {
                                *outfile << arg;
                            }
                            break;
                    }
                }

                std::string comment;
                std::getline(iss, comment);

                if (comment != "")
                {
                    *outfile << " ; " << comment;
                    // debug(comment);
                }
            }
            else if (num == 91)
            {
                *absolute = false;
                *outfile << line;
            }
            else if (num == 90)
            {
                *absolute = true;
                *outfile << line;
            }
            else
            {
                *outfile << line;
            }
        }
    }
    else
    {
        *outfile << line;
    }
    *outfile << *lineEnd;
}

std::string translate(double shifts[][2], int numShifts, std::string inPath,
                        std::string startRegex, std::string stopRegex, std::string version)
{
    std::ostringstream outPath;
    std::ostringstream op;

    op << ".translate_" << numShifts << "_shifts" << ".gcode";
    std::regex r("\\.g(co)*(de)*");
    outPath << std::regex_replace(inPath, r, op.str());

    std::ifstream infile(inPath);

    info("Working on file " + op.str());

    std::string line;
    std::ofstream outfile(outPath.str());

    std::regex start(startRegex);
    std::regex end(stopRegex);

    bool absolute = true;

    int afterStart = -1;

    std::string lineEnd = "\n";

    std::ostringstream layerStream;


    getline(infile, line);

    if (!line.empty() && line[line.size()-1] == '\r')
    {
        lineEnd = "\r\n";
    }

    outfile << "; Processed by OctoPrint-TranslateModel " << version << lineEnd << lineEnd;

    do
    {
        // Remove \r if file was CTLF
        if (!line.empty() && line[line.size()-1] == '\r')
        {
            line.erase(line.size()-1);
        }

        if (afterStart != 1)
        {
            if (std::regex_match(line, start))
            {
                afterStart = true;
                outfile << line << lineEnd << ";TRANSLATE-MODEL_LAYER_START" << lineEnd;
                layerStream = std::ostringstream();
            }
            else
            {
                outfile << line << lineEnd;
            }
        }
        else
        {
            if (std::regex_match(line, end))
            {
                afterStart = false;
                outfile << line << lineEnd << ";TRANSLATE-MODEL_STOP" << lineEnd;
            }
            else if (std::regex_match(line, start))
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
                        translateLine(shift, line, &outfile, abs, &lineEnd);
                    }

                    layerIStream.clear();
                    layerIStream.seekg(0);
                }

                absolute = *abs;
                delete abs;

                outfile << line << lineEnd << ";TRANSLATE-MODEL_LAYER_START" << lineEnd;
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
                    translateLine(shifts[0], line, &outfile, &absolute, &lineEnd);
                }
            }
        }
    }
    while (getline(infile, line));

    return outPath.str();
}

static PyObject *
translate_translate(PyObject *self, PyObject *args)
{
    PyObject *shiftList;

    const char *path, *sr, *er, *ver;

    if (!PyArg_ParseTuple(args, "Os(ss)s", &shiftList, &path,
                                            &sr, &er,
                                            &ver))
        return NULL;
    Py_INCREF(shiftList);

    PyObject *logging_message = Py_BuildValue("s", "tuple Parsed");
    Py_INCREF(logging_message);
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

    opath = translate(shifts, numShifts, (std::string) path,
                        (std::string) sr, (std::string) er, (std::string) ver);
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
translate_shift_test(PyObject *self, PyObject *args)
{
    PyObject *shiftList;

    if (!PyArg_ParseTuple(args, "O", &shiftList))
        return NULL;
    Py_INCREF(shiftList);

    PyObject *logging_message = Py_BuildValue("s", "tuple Parsed");
    Py_INCREF(logging_message);
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

    for (int i = 0; i < numShifts; i++)
    {
        std::cout << shifts[i][0] << ", " << shifts[i][1] << std::endl;
    }

    Py_RETURN_NONE;
}


static PyMethodDef TranslateMethods[] = {
    {"translate",  translate_translate, METH_VARARGS,
     "Translate a gcode file"},
    {"test",  translate_test, METH_VARARGS,
    "Just a test method"},
    {"shiftTest",  translate_shift_test, METH_VARARGS,
    "Shifts unpacking test method"},
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
