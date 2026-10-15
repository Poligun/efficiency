//! Composes greetings. A module library of the `hello` binary; the file is
//! the crate root and is named after its directory.

use std::fmt;

/// Why a name cannot be greeted. An error type derives the identity set,
/// hand-rolls `Display` and implements `Error`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GreetingError {
    /// The name was empty or whitespace only.
    EmptyName,
}

impl fmt::Display for GreetingError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyName => write!(f, "a name is required"),
        }
    }
}

impl std::error::Error for GreetingError {}

/// Returns the greeting for `name`, with surrounding whitespace removed.
///
/// # Errors
///
/// `GreetingError::EmptyName` when `name` is empty or whitespace only.
pub fn greet(name: &str) -> Result<String, GreetingError> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err(GreetingError::EmptyName);
    }
    Ok(format!("Hello, {trimmed}!"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greets_by_name() {
        assert_eq!(greet("Ada"), Ok("Hello, Ada!".to_owned()));
    }

    #[test]
    fn trims_whitespace() {
        assert_eq!(greet("  Ada "), Ok("Hello, Ada!".to_owned()));
    }

    #[test]
    fn refuses_an_empty_name() {
        assert_eq!(greet("   "), Err(GreetingError::EmptyName));
        assert_eq!(GreetingError::EmptyName.to_string(), "a name is required");
    }
}
