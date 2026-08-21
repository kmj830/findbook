package com.findbook.controller;

import com.findbook.service.BookDataService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class BookApiController {

    private final BookDataService bookDataService;

    @GetMapping("/targets")
    public ResponseEntity<Map<String, Object>> getTargets() {
        return ResponseEntity.ok(bookDataService.getTargetsData());
    }

    @PostMapping("/toggle_complete")
    public ResponseEntity<Map<String, Object>> toggleComplete(@RequestBody Map<String, String> request) {
        String code = request.get("code");
        return ResponseEntity.ok(bookDataService.toggleComplete(code));
    }

    @GetMapping("/search")
    public ResponseEntity<Map<String, Object>> search(@RequestParam(name = "code", required = false, defaultValue = "") String code) {
        return ResponseEntity.ok(bookDataService.search(code));
    }
}
