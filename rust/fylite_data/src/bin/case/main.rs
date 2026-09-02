//! `fylite-case` — a case from a fyo plan to a fyo record, as its own binary.
//!
//! A thin alias: the same spec-driven parser and the same bodies as
//! `fylite-app case …` (`fylite_data::cli::case`), with the `case` word
//! supplied here so `fylite-case run plan.jsonld` keeps working.  Usage and
//! refusals come from `_cli.json`, the one file the three hosts share
//! (FYL-DESIGN-15).

use fylite_data::cli::{self, Parsed};

fn main() {
    let mut argv: Vec<String> = vec!["case".into()];
    argv.extend(std::env::args().skip(1));
    let spec = cli::spec();
    match cli::parse(spec, cli::HOST, "fylite-case", &argv) {
        Parsed::Help(text) => print!("{}", text.replacen("fylite-case case", "fylite-case", 1)),
        Parsed::Error(msg) => {
            eprintln!("{}", msg.replacen("fylite-case case", "fylite-case", 1));
            std::process::exit(2);
        }
        Parsed::Run(args) => cli::case::run(&args),
    }
}
