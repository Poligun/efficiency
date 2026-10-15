//! The gRPC edge of the hello binary: the generated `Greeter` service,
//! implemented over the greeting module. Generated types are converted at
//! this boundary and go no deeper.

use greeting_proto::hello::v1::greeter_server::Greeter;
use greeting_proto::hello::v1::{GreetRequest, GreetResponse};
use hello_greeting::{GreetingError, greet};
use tonic::{Request, Response, Status};

/// The service handle. Dependencies arrive through the constructor and are
/// cloned per task; this one has none yet.
#[derive(Debug, Clone, Default)]
pub struct GreeterService;

/// Maps a domain error onto the gRPC status the contract promises.
fn status_of(error: &GreetingError) -> Status {
    match error {
        GreetingError::EmptyName => Status::invalid_argument(error.to_string()),
    }
}

#[tonic::async_trait]
impl Greeter for GreeterService {
    async fn greet(
        &self,
        request: Request<GreetRequest>,
    ) -> Result<Response<GreetResponse>, Status> {
        let greeting = greet(&request.into_inner().name).map_err(|error| status_of(&error))?;
        Ok(Response::new(GreetResponse { greeting }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn greets_over_the_wire_types() {
        let request = Request::new(GreetRequest {
            name: "Ada".to_owned(),
        });
        let response = GreeterService.greet(request).await.unwrap();
        assert_eq!(response.into_inner().greeting, "Hello, Ada!");
    }

    #[tokio::test]
    async fn an_empty_name_is_invalid_argument() {
        let request = Request::new(GreetRequest::default());
        let status = GreeterService.greet(request).await.unwrap_err();
        assert_eq!(status.code(), tonic::Code::InvalidArgument);
        assert_eq!(status.message(), "a name is required");
    }
}
