// 阻止 release 模式开 console 窗口
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    book_soul_lib::run();
}
