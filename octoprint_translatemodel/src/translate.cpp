#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <regex>

#include <fstream>
#include <sstream>
#include <string>
#include <iostream>

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

    std::string line;
    std::ofstream outfile(outPath.str());

    while (getline(infile, line))
    {
        // std::cout << "line: " << line << std::endl;

        std::istringstream iss(line);
        char cmd;
        int num;
        if ((iss >> cmd) && toupper(cmd) == 'G')
        {
            if ((iss >> num) && num >= 0 && num < 5)
            {
                outfile << "G" << num;
                char arg;
                float pos;
                while ((iss >> arg) && arg != ';')
                {
                    if (arg == '(')
                    {
                        outfile << arg;
                        do
                        {
                            iss >> arg;
                            outfile << arg;
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
            }
        }
        else
            outfile << line;
        outfile << std::endl;
    }

    return outPath.str();
}

// int main(int argc, char *argv[])
// {
//     if (argc > 3)
//     {
//
//         translate(std::stof(argv[1]), std::stof(argv[2]), (std::string) argv[3]);
//     }
//     else
//         return 1;
// }

static PyObject *
translate_translate(PyObject *self, PyObject *args)
{
    float xShift, yShift;
    const char *path;

    if (!PyArg_ParseTuple(args, "ffs", &xShift, &yShift, &path))
        return NULL;
    std::string opath = translate(xShift, yShift, (std::string) path);
    return Py_BuildValue("s", opath.c_str());
}

static PyObject *
translate_test(PyObject *self, PyObject *args)
{
    float xShift, yShift;

    if (!PyArg_ParseTuple(args, "ff", &xShift, &yShift))
        return NULL;
    std::cout << roundTo(3, xShift) << " " << roundTo(3, yShift) << std::endl;
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
    return PyModule_Create(&translatemodule);
}
