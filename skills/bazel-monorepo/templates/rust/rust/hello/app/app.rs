//! The application: turns command line arguments into a greeting. Everything
//! `main.rs` would otherwise do lives here, where it can be tested.

use std::fmt;

use hello_greeting::{GreetingError, greet};

/// Why the program could not produce a greeting.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AppError {
    /// No name was given on the command line.
    MissingName,
    /// The name was given but refused.
    Greeting(GreetingError),
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MissingName => write!(f, "usage: hello <name>"),
            Self::Greeting(error) => write!(f, "{error}"),
        }
    }
}

impl std::error::Error for AppError {}

/// Greets the first argument.
///
/// # Errors
///
/// `AppError::MissingName` when `args` is empty, and `AppError::Greeting`
/// when the greeting module refuses the name (an empty or blank name).
pub fn run(mut args: impl Iterator<Item = String>) -> Result<String, AppError> {
    let name = args.next().ok_or(AppError::MissingName)?;
    tracing::debug!(name, "greeting");
    greet(&name).map_err(AppError::Greeting)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greets_the_first_argument() {
        let args = ["Ada".to_owned(), "ignored".to_owned()];
        assert_eq!(run(args.into_iter()), Ok("Hello, Ada!".to_owned()));
    }

    #[test]
    fn refuses_no_argument() {
        assert_eq!(run(std::iter::empty()), Err(AppError::MissingName));
        assert_eq!(AppError::MissingName.to_string(), "usage: hello <name>");
    }

    #[test]
    fn passes_a_refused_name_through() {
        let result = run(std::iter::once("  ".to_owned()));
        assert_eq!(result, Err(AppError::Greeting(GreetingError::EmptyName)));
        assert_eq!(
            AppError::Greeting(GreetingError::EmptyName).to_string(),
            "a name is required"
        );
    }
}
