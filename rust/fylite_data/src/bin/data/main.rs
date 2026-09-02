//! `fylite-data` — the data layer's command line, as its own binary.
//!
//! A thin alias: the same spec-driven parser and the same bodies as
//! `fylite-app data …` (`fylite_data::cli::data`), with the `data` word
//! supplied here so `fylite-data info x` keeps working.  Usage and refusals
//! come from `_cli.json`, the one file the three hosts share (FYL-DESIGN-15).

use fylite_data::cli::{self, Parsed};

fn main() {
    let mut argv: Vec<String> = vec!["data".into()];
    argv.extend(std::env::args().skip(1));
    let spec = cli::spec();
    match cli::parse(spec, cli::HOST, "fylite-data", &argv) {
        Parsed::Help(text) => print!("{}", text.replacen("fylite-data data", "fylite-data", 1)),
        Parsed::Error(msg) => {
            eprintln!("{}", msg.replacen("fylite-data data", "fylite-data", 1));
            std::process::exit(2);
        }
        Parsed::Run(args) => cli::data::run(&args),
    }
}
