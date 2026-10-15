//! The entry point. It cannot be unit tested, so it holds no logic: it hands
//! the arguments to `hello_app::run`, prints the result, and turns an error
//! into an exit code.

use std::process::ExitCode;

#[allow(
    clippy::print_stdout,
    clippy::print_stderr,
    reason = "the greeting is the program's output, and the final error has nowhere else to go"
)]
fn main() -> ExitCode {
    match hello_app::run(std::env::args().skip(1)) {
        Ok(greeting) => {
            println!("{greeting}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("hello: {error}");
            ExitCode::FAILURE
        }
    }
}
