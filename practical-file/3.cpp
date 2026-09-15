#include <iostream>
#include <cmath>
using namespace std;
class Complex {
private:
    double real;
    double imag;

public:
    Complex() : real(0.0), imag(0.0) {}

    Complex(double r, double i) : real(r), imag(i) {}

    Complex(double r) : real(r), imag(0.0) {}
    
    Complex(int r) : real(static_cast<double>(r)), imag(0.0) {}

    Complex operator+(const Complex& other) const {
        return Complex(real + other.real, imag + other.imag);
    }

    Complex operator-(const Complex& other) const {
        return Complex(real - other.real, imag - other.imag);
    }

    Complex operator*(const Complex& other) const {
        return Complex(
            real * other.real - imag * other.imag, 
            real * other.imag + imag * other.real
        );
    }

    explicit operator double() const {
        return sqrt(real * real + imag * imag);
    }

    friend std::ostream& operator<<(std::ostream& os, const Complex& c);
};

std::ostream& operator<<(std::ostream& os, const Complex& c) {
    os << c.real;
    if (c.imag >= 0) {
        os << " + " << c.imag << "i";
    } else {
        os << " - " << std::abs(c.imag) << "i";
    }
    return os;
}
int main() {
    cout << "### Complex Number Operations ###\n";

    Complex a(3.0, 4.0); 
    Complex b(1.0, -2.0); 
    cout << "A = " << a << "\n";
    cout << "B = " << b << "\n";

    Complex sum = a + b;
    cout << "A + B = " << sum << "\n"; 

    Complex product = a * b;
    cout << "A * B = " << product << "\n"; 

    cout << "\n";

    Complex c_from_int = 5;
    Complex c_from_double = -2.5;
    cout << "Complex from int (5): " << c_from_int << "\n";
    cout << "Complex from double (-2.5): " << c_from_double << "\n";

    Complex mixed_sum = a + b; 
    cout << "A + B = " << mixed_sum << "\n"; 

    double mag_a = static_cast<double>(a); 
    cout << "Magnitude of A (|A|) = " << mag_a << "\n";
    
    return 0;
}