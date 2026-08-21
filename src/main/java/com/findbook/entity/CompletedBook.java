package com.findbook.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "completed_books")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CompletedBook {

    @Id
    @Column(name = "reg_no", length = 50, nullable = false)
    private String regNo;

    @Builder.Default
    @Column(name = "completed_at", nullable = false)
    private LocalDateTime completedAt = LocalDateTime.now();
}
