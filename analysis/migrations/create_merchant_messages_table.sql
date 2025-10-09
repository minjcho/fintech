-- Create merchant_messages table
CREATE TABLE IF NOT EXISTS merchant_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    merchant VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    message VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_merchant (merchant),
    INDEX idx_message_type (message_type),
    UNIQUE KEY uq_merchant_type (merchant, message_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sample data
INSERT INTO merchant_messages (merchant, message_type, message) VALUES
('스타벅스', 'most_spent', '커피 지출이 많네요! 텀블러를 활용해보세요'),
('스타벅스', 'most_frequent', '자주 방문하시네요! 리워드 혜택을 확인해보세요'),
('김밥천국', 'most_spent', '외식비 절약을 위해 가끔은 집밥을 드셔보세요'),
('김밥천국', 'most_frequent', '자주 가시네요! 쿠폰이나 할인 혜택을 찾아보세요'),
('GS칼텍스', 'most_spent', '주유비가 많이 나가네요! 대중교통 이용도 고려해보세요'),
('GS칼텍스', 'most_frequent', '자주 주유하시네요! 주유 할인카드를 활용하세요'),
('카카오택시', 'most_spent', '택시비 지출이 큽니다! 대중교통을 이용해보세요'),
('카카오택시', 'most_frequent', '택시를 자주 이용하시네요! 카풀이나 대중교통도 고려해보세요'),
('CGV', 'most_spent', '영화 관람 비용이 많네요! 할인 시간대를 이용해보세요'),
('CGV', 'most_frequent', '영화를 자주 보시네요! 멤버십 혜택을 확인하세요'),
('넷플릭스', 'most_spent', '구독료를 절약하려면 가족 공유를 고려해보세요'),
('넷플릭스', 'most_frequent', '구독 서비스를 잘 활용하고 계시네요!')
ON DUPLICATE KEY UPDATE message = VALUES(message);