package com.findbook.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.findbook.entity.CompletedBook;
import com.findbook.repository.CompletedBookRepository;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.InputStream;
import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class BookDataService {

    private final CompletedBookRepository completedBookRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private Map<String, Map<String, Object>> allBarcodes = new HashMap<>();
    private Map<String, List<Map<String, Object>>> lineSequences = new HashMap<>();
    private Map<String, Map<String, Object>> targets = new HashMap<>();

    @PostConstruct
    public void init() {
        try {
            ClassPathResource resource = new ClassPathResource("data.json");
            try (InputStream is = resource.getInputStream()) {
                Map<String, Object> root = objectMapper.readValue(is, new TypeReference<Map<String, Object>>() {});
                
                this.allBarcodes = (Map<String, Map<String, Object>>) root.get("all_barcodes");
                this.lineSequences = (Map<String, List<Map<String, Object>>>) root.get("line_sequences");
                this.targets = (Map<String, Map<String, Object>>) root.get("targets");
                
                log.info("Loaded data.json successfully: {} barcodes, {} line sequences, {} targets",
                        allBarcodes.size(), lineSequences.size(), targets.size());
            }
        } catch (Exception e) {
            log.error("Failed to load data.json", e);
        }
    }

    public Map<String, Object> getTargetsData() {
        Set<String> completedSet = completedBookRepository.findAllRegNos();

        List<Map<String, Object>> sgList = new ArrayList<>();
        List<Map<String, Object>> pgList = new ArrayList<>();
        List<Map<String, Object>> completedList = new ArrayList<>();

        for (Map.Entry<String, Map<String, Object>> entry : targets.entrySet()) {
            String code = entry.getKey();
            Map<String, Object> item = new HashMap<>(entry.getValue());
            boolean isCompleted = completedSet.contains(code);
            item.put("is_completed", isCompleted);

            if (isCompleted) {
                completedList.add(item);
            } else {
                String type = (String) item.get("type");
                if ("서가배열".equals(type)) {
                    sgList.add(item);
                } else {
                    pgList.add(item);
                }
            }
        }

        Comparator<Map<String, Object>> sortComparator = (a, b) -> {
            String subLineA = (String) a.get("sub_line");
            String subLineB = (String) b.get("sub_line");
            int subIdxA = ((Number) a.get("sub_idx")).intValue();
            int subIdxB = ((Number) b.get("sub_idx")).intValue();

            String[] partsA = subLineA.split("-");
            String[] partsB = subLineB.split("-");

            int lineA = partsA[0].matches("\\d+") ? Integer.parseInt(partsA[0]) : 999;
            int lineB = partsB[0].matches("\\d+") ? Integer.parseInt(partsB[0]) : 999;
            if (lineA != lineB) return Integer.compare(lineA, lineB);

            int subPartA = partsA.length > 1 && partsA[1].matches("\\d+") ? Integer.parseInt(partsA[1]) : 0;
            int subPartB = partsB.length > 1 && partsB[1].matches("\\d+") ? Integer.parseInt(partsB[1]) : 0;
            if (subPartA != subPartB) return Integer.compare(subPartA, subPartB);

            return Integer.compare(subIdxA, subIdxB);
        };

        sgList.sort(sortComparator);
        pgList.sort(sortComparator);
        completedList.sort(sortComparator);

        int totalCount = targets.size();
        int completedCount = completedList.size();
        int remainingCount = totalCount - completedCount;
        double progressPct = totalCount > 0 ? Math.round((double) completedCount / totalCount * 1000.0) / 10.0 : 0.0;

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("cloud_storage", true);
        response.put("total_count", totalCount);
        response.put("completed_count", completedCount);
        response.put("remaining_count", remainingCount);
        response.put("progress_pct", progressPct);
        response.put("sg_list", sgList);
        response.put("pg_list", pgList);
        response.put("completed_list", completedList);

        return response;
    }

    @Transactional
    public Map<String, Object> toggleComplete(String code) {
        if (code == null || code.trim().isEmpty()) {
            return Map.of("success", false, "error", "등록번호가 필요합니다.");
        }
        code = code.trim().toUpperCase();

        boolean exists = completedBookRepository.existsById(code);
        boolean isCompleted;

        if (exists) {
            completedBookRepository.deleteById(code);
            isCompleted = false;
        } else {
            completedBookRepository.save(CompletedBook.builder()
                    .regNo(code)
                    .completedAt(LocalDateTime.now())
                    .build());
            isCompleted = true;
        }

        Map<String, Object> res = new HashMap<>();
        res.put("success", true);
        res.put("code", code);
        res.put("is_completed", isCompleted);
        return res;
    }

    public Map<String, Object> search(String queryCode) {
        if (queryCode == null || queryCode.trim().isEmpty()) {
            return Map.of("success", false, "error", "등록번호를 입력해주세요.");
        }
        String code = queryCode.trim().toUpperCase();

        if (!allBarcodes.containsKey(code)) {
            final String searchTarget = code;
            Optional<String> match = allBarcodes.keySet().stream()
                    .filter(k -> k.contains(searchTarget))
                    .findFirst();
            if (match.isPresent()) {
                code = match.get();
            } else {
                return Map.of("success", false, "error", "바코드 [" + code + "]를 찾을 수 없습니다. 등록번호를 다시 확인해주세요.");
            }
        }

        Set<String> completedSet = completedBookRepository.findAllRegNos();
        Map<String, Object> curr = allBarcodes.get(code);
        boolean isTarget = targets.containsKey(code);
        Map<String, Object> targetInfo = targets.get(code);
        boolean isCurrCompleted = completedSet.contains(code);

        String subLine = (String) curr.get("sub_line");
        int currSubIdx = ((Number) curr.get("sub_idx")).intValue();
        List<Map<String, Object>> subSeq = lineSequences.getOrDefault(subLine, Collections.emptyList());

        List<Map<String, Object>> targetsInLine = new ArrayList<>();
        for (Map<String, Object> item : subSeq) {
            String itemCode = (String) item.get("code");
            if (targets.containsKey(itemCode) && !completedSet.contains(itemCode)) {
                int itemSubIdx = ((Number) item.get("sub_idx")).intValue();
                int diff = itemSubIdx - currSubIdx;
                int distance = Math.abs(diff);

                String directionText;
                String directionBadge;
                if (diff == 0) {
                    directionText = "🎯 바로 현재 이 책입니다!";
                    directionBadge = "현재 도서";
                } else if (diff > 0) {
                    directionText = "➡️ 뒤로 " + diff + "번째 책 (" + diff + "권 뒤)";
                    directionBadge = "뒤로 " + diff + "권";
                } else {
                    directionText = "⬅️ 앞으로 " + (-diff) + "번째 책 (" + (-diff) + "권 앞)";
                    directionBadge = "앞으로 " + (-diff) + "권";
                }

                Map<String, Object> tObj = new HashMap<>();
                tObj.put("reg_no", itemCode);
                tObj.put("diff", diff);
                tObj.put("distance", distance);
                tObj.put("direction_text", directionText);
                tObj.put("direction_badge", directionBadge);
                tObj.put("info", targets.get(itemCode));
                tObj.put("loc_desc", item.get("loc_desc"));
                tObj.put("sub_idx", itemSubIdx);

                targetsInLine.add(tObj);
            }
        }

        List<Map<String, Object>> targetsByDistance = new ArrayList<>(targetsInLine);
        targetsByDistance.sort(Comparator.comparingInt(a -> ((Number) a.get("distance")).intValue()));

        List<Map<String, Object>> targetsByPosition = new ArrayList<>(targetsInLine);
        targetsByPosition.sort(Comparator.comparingInt(a -> ((Number) a.get("sub_idx")).intValue()));

        Map<String, Object> closestPrev = null;
        Map<String, Object> closestNext = null;

        for (Map<String, Object> t : targetsByPosition) {
            int diff = ((Number) t.get("diff")).intValue();
            if (diff < 0) {
                closestPrev = t;
            } else if (diff > 0 && closestNext == null) {
                closestNext = t;
            }
        }

        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("query_code", code);
        response.put("current_book", curr);
        response.put("is_target", isTarget);
        response.put("target_info", targetInfo);
        response.put("is_curr_completed", isCurrCompleted);
        response.put("targets_count_in_line", targetsInLine.size());
        response.put("closest_prev", closestPrev);
        response.put("closest_next", closestNext);
        response.put("targets_by_distance", targetsByDistance);
        response.put("targets_by_position", targetsByPosition);

        return response;
    }
}
