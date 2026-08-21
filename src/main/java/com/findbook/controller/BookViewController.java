package com.findbook.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class BookViewController {

    @GetMapping("/")
    public String index() {
        return "index";
    }
}
