#include <iostream>
using namespace std;

class Vector;

class Matrix {
private:
    static const int MAX_ROWS = 3;
    static const int MAX_COLS = 3;
    int data[MAX_ROWS][MAX_COLS];
    int rows, cols;

public:
    Matrix(int r = 3, int c = 3) : rows(r), cols(c) {
        for (int i = 0; i < rows; i++)
            for (int j = 0; j < cols; j++)
                data[i][j] = 0;
    }

    void setElement(int r, int c, int val) {
        if(r < rows && c < cols)
            data[r][c] = val;
        else
            cout << "Index out of bounds!" << endl;
    }

    void print() const {
        for (int i = 0; i < rows; i++) {
            for (int j = 0; j < cols; j++)
                cout << data[i][j] << " ";
            cout << endl;
        }
    }

    friend Vector multiply(const Matrix& m, const Vector& v);
};

class Vector {
private:
    static const int MAX_SIZE = 3;
    int data[MAX_SIZE];
    int size;

public:
    Vector(int s = 3) : size(s) {
        for (int i = 0; i < size; i++)
            data[i] = 0;
    }

    void setElement(int i, int val) {
        if(i < size)
            data[i] = val;
        else
            cout << "Index out of bounds!" << endl;
    }

    void print() const {
        for (int i = 0; i < size; i++)
            cout << data[i] << " ";
        cout << endl;
    }

    friend Vector multiply(const Matrix& m, const Vector& v);
};

Vector multiply(const Matrix& m, const Vector& v) {
    Vector result;
    for (int i = 0; i < Matrix::MAX_ROWS; i++) {
        int sum = 0;
        for (int j = 0; j < Matrix::MAX_COLS; j++)
            sum += m.data[i][j] * v.data[j];
        result.data[i] = sum;
    }
    return result;
}

int main() {
    Matrix m;
    Vector v;

    m.setElement(0, 0, 1);
    m.setElement(0, 1, 2);
    m.setElement(0, 2, 3);
    m.setElement(1, 0, 4);
    m.setElement(1, 1, 5);
    m.setElement(1, 2, 6);
    m.setElement(2, 0, 7);
    m.setElement(2, 1, 8);
    m.setElement(2, 2, 9);

    v.setElement(0, 1);
    v.setElement(1, 2);
    v.setElement(2, 3);

    cout << "Matrix:" << endl;
    m.print();

    cout << "Vector:" << endl;
    v.print();

    Vector result = multiply(m, v);
    cout << "Result (Matrix * Vector):" << endl;
    result.print();

    return 0;
}
