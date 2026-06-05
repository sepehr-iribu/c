package hello

// Version of the package.
const Version = "1.0.0"

// DefaultPrefix used for greetings.
var DefaultPrefix = "Hello"

// Greeter renders greetings.
type Greeter struct {
    Prefix string
}

// Speaker is behavior that can speak.
type Speaker interface {
    Speak(name string) string
}

// NewGreeter creates a greeter.
func NewGreeter(prefix string) Greeter {
    return Greeter{Prefix: prefix}
}

// Speak renders a greeting.
func (g *Greeter) Speak(name string) string {
    return g.Prefix + ", " + name
}
