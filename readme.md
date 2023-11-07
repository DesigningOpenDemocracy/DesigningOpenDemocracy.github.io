# Designing Open Democracy Wiki

This book is a collection of concepts and events that Designing Open Democracy would like to compile for reference.

This book is using [mdBook](https://github.com/rust-lang/mdBook), a utility to create modern online books from markdown files.

## Prerequisites

Before you can use `mdBook`, you must ensure you have the following:

- [Rust](https://www.rust-lang.org/tools/install) programming language
- Cargo, which is included with Rust by default

After installing Rust and Cargo, you can install `mdBook` with the following command:

```shell
cargo install mdbook
```

## Quick Start

Here's how you can get started:

1. **Build the book:**

   Run `make build` to compile the book into HTML files that you can view in your web browser.

2. **Serve the book:**

   Run `make serve` to start a local web server and open the book in your default browser.

3. **Clean build artifacts:**

   Run `make clean` to remove any generated files from the `book` directory.

## Contributing

To contribute to this book:

1. Clone the repository.
2. Create a branch for your changes.
3. Make your changes to the markdown files.
4. Build and test your changes locally using the Makefile commands.
5. Commit your changes and open a pull request.

## Further Information

For comprehensive documentation on `mdBook`, please refer to the official [mdBook User Guide](https://rust-lang.github.io/mdBook/).
