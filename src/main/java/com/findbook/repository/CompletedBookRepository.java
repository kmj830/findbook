package com.findbook.repository;

import com.findbook.entity.CompletedBook;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Set;

@Repository
public interface CompletedBookRepository extends JpaRepository<CompletedBook, String> {

    @Query("SELECT c.regNo FROM CompletedBook c")
    Set<String> findAllRegNos();
}
