#include <iostream>
using namespace std;

class Matrix {
private:
    int rows;
    int cols;
    int** data;

public:
    Matrix(int r = 3, int c = 3) : rows(r), cols(c) {
        data = new int*[rows];
        for (int i = 0; i < rows; i++) {
            data[i] = new int[cols];
            for (int j = 0; j < cols; j++)
                data[i][j] = 0;
        }
    }

    Matrix(const Matrix& m) : rows(m.rows), cols(m.cols) {
        data = new int*[rows];
        for (int i = 0; i < rows; i++) {
            data[i] = new int[cols];
            for (int j = 0; j < cols; j++)
                data[i][j] = m.data[i][j];
        }
    }

    Matrix& operator=(const Matrix& m) {
        if (this == &m)
            return *this;

        for (int i = 0; i < rows; i++)
            delete[] data[i];
        delete[] data;

        rows = m.rows;
        cols = m.cols;
        data = new int*[rows];
        for (int i = 0; i < rows; i++) {
            data[i] = new int[cols];
            for (int j = 0; j < cols; j++)
                data[i][j] = m.data[i][j];
        }
        return *this;
    }

    ~Matrix() {
        for (int i = 0; i < rows; i++)
            delete[] data[i];
        delete[] data;
    }

    void setElement(int r, int c, int val) {
        if (r >= 0 && r < rows && c >= 0 && c < cols)
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
};

int main() {
    Matrix m1(2, 2);
    m1.setElement(0, 0, 6);
    m1.setElement(0, 1, 10);
    m1.setElement(1, 0, 19);
    m1.setElement(1, 1, 20);

    cout << "Matrix m1:" << endl;
    m1.print();

    Matrix m2 = m1;  // Copy constructor
    cout << "Matrix m2 (copy of m1):" << endl;
    m2.print();

    Matrix m3;
    m3 = m1;  // Assignment operator
    cout << "Matrix m3 (assigned from m1):" << endl;
    m3.print();

    return 0;
}
