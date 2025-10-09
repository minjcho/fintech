-- Initialize database schema for fintech AI services
-- Create database if not exists
CREATE DATABASE IF NOT EXISTS fintech_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE fintech_ai;

-- Create predictions table for storing Prophet forecast results
CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    prediction_date DATE NOT NULL,
    predicted_amount DECIMAL(15, 2) NOT NULL,
    lower_bound DECIMAL(15, 2),
    upper_bound DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_file_cat_date (file_id, category, prediction_date),
    INDEX idx_file_id (file_id),
    INDEX idx_category (category),
    INDEX idx_prediction_date (prediction_date)
);

-- Create analysis_jobs table for tracking async jobs
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    file_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message VARCHAR(1000),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    job_metadata JSON,
    INDEX idx_jobs_file_id (file_id),
    INDEX idx_jobs_status (status)
);

-- Create baseline_predictions table for storing monthly baseline predictions
CREATE TABLE IF NOT EXISTS baseline_predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    predicted_amount DECIMAL(15, 2) NOT NULL,
    lower_bound DECIMAL(15, 2),
    upper_bound DECIMAL(15, 2),
    training_cutoff_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_baseline_file_cat_year_month (file_id, category, year, month),
    INDEX idx_baseline_file_id (file_id),
    INDEX idx_baseline_category (category),
    INDEX idx_baseline_year_month (year, month)
);

-- Create leak_analysis table for storing leak calculation results
CREATE TABLE IF NOT EXISTS leak_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    actual_amount DECIMAL(15, 2),
    predicted_amount DECIMAL(15, 2),
    leak_amount DECIMAL(15, 2),
    analysis_data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_file_year_month (file_id, year, month),
    INDEX idx_leak_file_id (file_id),
    INDEX idx_leak_year_month (year, month)
);

-- Create doojo_analysis table for storing category spending thresholds
CREATE TABLE IF NOT EXISTS doojo_analysis (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    min_amount DECIMAL(15, 2) NOT NULL,
    max_amount DECIMAL(15, 2) NOT NULL,
    current_threshold DECIMAL(15, 2) NOT NULL,
    real_amount DECIMAL(15, 2),
    result VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_doojo_file_cat_year_month (file_id, category, year, month),
    INDEX idx_doojo_file_id (file_id),
    INDEX idx_doojo_category (category),
    INDEX idx_doojo_year_month (year, month)
);