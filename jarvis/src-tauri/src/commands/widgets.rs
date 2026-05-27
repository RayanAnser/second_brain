use serde::Serialize;
use std::{fs, path::PathBuf};

fn memory_dir() -> PathBuf {
    PathBuf::from(std::env::var("MEMORY_DIR").unwrap_or_else(|_| "./memory".to_string()))
}

fn read_file(name: &str) -> String {
    fs::read_to_string(memory_dir().join(name)).unwrap_or_default()
}

#[derive(Serialize)]
pub struct AgendaItem {
    pub time:  String,
    pub label: String,
}

#[derive(Serialize)]
pub struct ProjectItem {
    pub name:   String,
    pub status: String,
}

#[derive(Serialize)]
pub struct WidgetsContext {
    pub agenda:   Vec<AgendaItem>,
    pub projects: Vec<ProjectItem>,
    pub threads:  Vec<String>,
    pub taches:   Vec<String>,
}

fn parse_agenda(content: &str) -> Vec<AgendaItem> {
    // Only show items from today onward. Sections are ## YYYY-MM-DD.
    let today = chrono::Local::now().format("%Y-%m-%d").to_string();
    let mut items = Vec::new();
    let mut cur_date = String::new();

    for line in content.lines() {
        if line.starts_with("## ") {
            cur_date = line[3..].trim().to_string();
            continue;
        }
        if cur_date < today && !cur_date.is_empty() { continue; }
        if !line.starts_with("- ") { continue; }
        let s = line[2..].trim();
        let mut it = s.splitn(2, " | ");
        let time  = it.next().unwrap_or("").trim().to_string();
        let label = it.next().unwrap_or("").trim().to_string();
        if time.contains(':') && !label.is_empty() {
            items.push(AgendaItem { time, label });
        }
    }
    items
}

fn shorten_name(name: &str) -> String {
    name.split('(').next().unwrap_or(name)
        .split(" —").next().unwrap_or(name)
        .trim()
        .to_string()
}

fn parse_projects(content: &str) -> Vec<ProjectItem> {
    let mut projects: Vec<ProjectItem> = Vec::new();
    let mut in_section = false;
    let mut cur_name   = String::new();
    let mut cur_status = String::new();

    for line in content.lines() {
        if !in_section {
            if line.contains("Projets actifs") { in_section = true; }
            continue;
        }
        if line.starts_with("---") || (line.starts_with("## ") && !line.contains("Projets actifs")) {
            if !cur_name.is_empty() {
                projects.push(ProjectItem { name: shorten_name(&cur_name), status: cur_status.clone() });
                cur_name.clear();
            }
            break;
        }
        if line.starts_with("### ") {
            if !cur_name.is_empty() {
                projects.push(ProjectItem { name: shorten_name(&cur_name), status: cur_status.clone() });
            }
            cur_name   = line[4..].trim().to_string();
            cur_status = String::new();
        } else if line.contains("**Statut**") && cur_status.is_empty() {
            if let Some(idx) = line.find(": ") {
                let raw = line[idx + 2..].trim().trim_matches('*');
                cur_status = raw.split(" — ").next().unwrap_or(raw).trim().to_string();
            }
        }
    }
    if !cur_name.is_empty() {
        projects.push(ProjectItem { name: shorten_name(&cur_name), status: cur_status });
    }
    projects
}

fn parse_taches(content: &str) -> Vec<String> {
    let mut taches = Vec::new();
    let mut in_section = false;
    for line in content.lines() {
        if !in_section {
            if line.trim() == "## En cours" { in_section = true; }
            continue;
        }
        if line.starts_with("## ") { break; }
        if line.starts_with("- ") {
            let raw = line[2..].trim();
            let clean = raw.split("  _(").next().unwrap_or(raw).trim().to_string();
            if !clean.is_empty() { taches.push(clean); }
        }
    }
    taches
}

fn parse_threads(content: &str) -> Vec<String> {
    let mut threads     = Vec::new();
    let mut in_section  = false;
    for line in content.lines() {
        if !in_section {
            if line.trim().starts_with("## ") && line.contains("Fils ouverts") { in_section = true; }
            continue;
        }
        if line.starts_with("---") || line.starts_with("## ") { break; }
        if line.starts_with("- ") {
            threads.push(line[2..].trim().to_string());
        }
    }
    threads
}

#[tauri::command]
pub fn read_widgets_context() -> WidgetsContext {
    let memory = read_file("memory.md");
    WidgetsContext {
        agenda:   parse_agenda(&read_file("agenda.md")),
        projects: parse_projects(&memory),
        threads:  parse_threads(&memory),
        taches:   parse_taches(&read_file("taches.md")),
    }
}
