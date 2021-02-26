#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <regex>

#include <fstream>
#include <sstream>
#include <string>
#include <iostream>

static char module_name[] = "octoprint.plugins.translatemodel-C++";
static PyObject *logging_library = NULL;
static PyObject *logging_object= NULL;
static PyThreadState *_save;

void info(std::string msg)
{
    Py_BLOCK_THREADS
    PyObject *logging_message = Py_BuildValue("s", msg.c_str());
    Py_XINCREF(logging_message);

    std::cout << "Got past message build" << std::endl;

    std::cout << "LO: " << logging_object << std::endl;
    PyObject_CallMethod(logging_object, "info", "O", logging_message, NULL);
    std::cout << "Got past CallMethod" << std::endl;


    Py_DECREF(logging_message);
    Py_UNBLOCK_THREADS
}

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
    int n, pointCount = 0;
    std::string val = "";
    while ((n = stream->peek()) && pointCount < 2)
    {
        // std::cout << (char) n << " pc: " << pointCount << std::endl;
        if (n > 47 && n <= 57)
        {
            val += stream->get();
        }
        else if (n == 46)
        {
            pointCount++;
            if (pointCount < 2)
                val += stream->get();
        }
        else
            break;
    }

    if (val != "")
        return std::stof(val);
    else
        return NAN;
}

std::string translate(float xShift, float yShift, std::string inPath)
{
    std::ostringstream outPath;
    std::ostringstream op;

    op << ".translate_" << xShift << "_" << yShift << ".gcode";
    std::regex r(".g(co)*(de)*");
    outPath << std::regex_replace(inPath, r, op.str());

    std::ifstream infile(inPath);

    info("Working on file " + op.str());

    std::string line;
    std::ofstream outfile(outPath.str());

    std::regex objStart("^; printing object !(ENDGCODE)");
    std::regex objEnd("^; stop printing object !(ENDGCODE)");

    std::regex start(";(AFTER_LAYER_CHANGE|LAYER:0)");
    std::regex end("end");

    int inObj = -1;
    int afterStart = -1;


    while (getline(infile, line))
    {
        debug(line);

        if (inObj == -1 && afterStart == -1)
        {
            if (std::regex_match(line, objStart))
                inObj = true;
            else if (std::regex_match(line, start))
                afterStart = true;
            outfile << line << std::endl;
            debug("proc: -1 -1");
        }
        else if (inObj == 0)
        {
            if (std::regex_match(line, objStart))
                inObj = true;
            debug("proc: 0 *");
        }
        else if (afterStart == 0)
        {
            if (std::regex_match(line, start))
                afterStart = true;
            debug("proc: -1 0");
        }
        else
        {
            if (std::regex_match(line, objEnd))
                inObj = false;
            else if (std::regex_match(line, end))
                afterStart = false;
            std::istringstream iss(line);
            char cmd;
            int num;
            if ((iss >> cmd) && toupper(cmd) == 'G')
            {
                if ((iss >> num) && num >= 0 && num < 4)
                {
                    outfile << "G" << num;
                    char arg;
                    float pos;
                    while ((iss >> arg) && arg != ';')
                    {
                        if (arg == '(')
                        {
                            outfile << arg;
                            std::cout << arg;
                            do
                            {
                                iss >> arg;
                                outfile << arg;
                                std::cout << arg;
                            }
                            while (arg != ')');
                        }
                        else
                        {
                            pos = parseFloat(&iss);
                            if (!isnan(pos))
                            {
                                switch (toupper(arg))
                                {
                                    case 'X':
                                        outfile << " " << arg << roundTo(3, (pos+xShift));
                                        break;
                                    case 'Y':
                                        outfile << " " << arg << roundTo(3, (pos+yShift));
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
                        debug(comment);
                    }
                }
            }
            else
            {
                outfile << line;
            }
            outfile << std::endl;
        }
    }

    return outPath.str();
}

static PyObject *
translate_translate(PyObject *self, PyObject *args)
{
    float xShift, yShift;
    const char *path;

    if (!PyArg_ParseTuple(args, "ffs", &xShift, &yShift, &path))
        return NULL;
    std::string opath;
    Py_UNBLOCK_THREADS
    opath = translate(xShift, yShift, (std::string) path);
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
    std::cout << "LO: " << logging_object << std::endl;

    return PyModule_Create(&translatemodule);
}
