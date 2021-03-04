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

std::string translate(float xShift, float yShift, std::string inPath,
                        std::string objStartRegex, std::string objStopRegex,
                        std::string startRegex, std::string stopRegex)
{
    std::ostringstream outPath;
    std::ostringstream op;

    op << ".translate_" << xShift << "_" << yShift << ".gcode";
    std::regex r("\\.g(co)*(de)*");
    outPath << std::regex_replace(inPath, r, op.str());

    std::ifstream infile(inPath);

    // info("Working on file " + op.str());

    std::string line;
    std::ofstream outfile(outPath.str());

    std::regex objStart(objStartRegex);
    std::regex objEnd(objStopRegex);

    std::regex start(startRegex);
    std::regex end(stopRegex);

    bool absolute = true;

    int inObj = -1;
    int afterStart = -1;


    std::string lineEnd = "\n";

    getline(infile, line);

    if (!line.empty() && line[line.size()-1] == '\r')
    {
        lineEnd = "\r\n";
    }

    outfile << "; Processed by OctoPrint-TranslateModel" << lineEnd << lineEnd;

    do
    {
        // Remove \r if file was CTLF
        if (!line.empty() && line[line.size()-1] == '\r')
        {
            line.erase(line.size()-1);
        }

        if (inObj == -1 && afterStart != 1)
        {
            if (std::regex_match(line, objStart))
            {
                inObj = true;
                outfile << line << lineEnd << ";TRANSLATE-MODEL_OBJECT-START" << lineEnd;
            }
            else if (std::regex_match(line, start))
            {
                afterStart = true;
                outfile << line << lineEnd << ";TRANSLATE-MODEL_LAYER-START" << lineEnd;
            }
            else
            {
                outfile << line << lineEnd;
            }
        }
        else if (inObj == 0)
        {
            if (std::regex_match(line, objStart))
            {
                inObj = true;
                outfile << line << lineEnd << ";TRANSLATE-MODEL_OBJECT-START" << lineEnd;
            }
        }
        else
        {
            if (std::regex_match(line, objEnd))
            {
                inObj = false;
                outfile << line << lineEnd << ";TRANSLATE-MODEL_OBJECT-STOP" << lineEnd;
            }
            else if (std::regex_match(line, end))
            {
                afterStart = false;
                outfile << line << lineEnd << ";TRANSLATE-MODEL_END-STOP" << lineEnd;
            }
            else
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
                            outfile << "G" << num;
                            char arg;
                            float pos;
                            while ((iss >> arg) && arg != ';')
                            {
                                if (arg == '(')
                                {
                                    outfile << arg;
                                    // std::cout << arg;
                                    do
                                    {
                                        iss >> arg;
                                        outfile << arg;
                                        // std::cout << arg;
                                    }
                                    while (arg != ')');
                                }
                                else if (toupper(arg) > 'A' && toupper(arg) <= 'Z')
                                {
                                    pos = parseFloat(&iss);
                                    if (!isnan(pos))
                                    {
                                        switch (toupper(arg))
                                        {
                                            case 'X':
                                                if (absolute)
                                                    outfile << " " << arg << roundTo(3, (pos+xShift));
                                                else
                                                    outfile << " " << arg << roundTo(3, pos);
                                                break;
                                            case 'Y':
                                                if (absolute)
                                                    outfile << " " << arg << roundTo(3, (pos+yShift));
                                                else
                                                    outfile << " " << arg << roundTo(3, pos);
                                                break;
                                            case 'E':
                                                outfile << " " << arg << roundTo(5, pos);
                                                break;
                                            default:
                                                outfile << " " << arg << roundTo(3, pos);
                                                break;
                                        }
                                    }
                                    else
                                        outfile << " " << arg;
                                }
                            }

                            std::string comment;
                            std::getline(iss, comment);

                            if (comment != "")
                            {
                                outfile << " ; " << comment;
                                // debug(comment);
                            }
                        }
                        else if (num == 91)
                        {
                            absolute = false;
                        }
                        else if (num == 90)
                        {
                            absolute = true;
                        }
                    }
                }
                else
                {
                    outfile << line;
                }
                outfile << lineEnd;
            }
        }
    }
    while (getline(infile, line));

    return outPath.str();
}

static PyObject *
translate_translate(PyObject *self, PyObject *args)
{
    float xShift, yShift;
    const char *path, *osr, *oer, *sr, *er;

    if (!PyArg_ParseTuple(args, "ffs(ssss)", &xShift, &yShift, &path,
                                            &osr, &oer, &sr, &er))
        return NULL;
    std::string opath;
    Py_UNBLOCK_THREADS
    opath = translate(xShift, yShift, (std::string) path,
                        (std::string) osr, (std::string) oer,
                        (std::string) sr, (std::string) er);
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


static PyMethodDef TranslateMethods[] = {
    {"translate",  translate_translate, METH_VARARGS,
     "Translate a gcode file"},
    {"test",  translate_test, METH_VARARGS,
    "Just a test method"},
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
