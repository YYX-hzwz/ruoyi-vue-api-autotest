-- 测试环境专用配置（仅用于 docker 起的本地测试库，不要用于生产）
--
-- RuoYi 3.9.x 的验证码开关有两处来源：
--   1) application.yml 的 ruoyi.captchaEnabled
--   2) 数据库 sys_config.sys.account.captchaEnabled
-- 实际生效的是第 2 处（SysConfigService.selectCaptchaEnabled）。
-- 这就是原项目"改配置文件不生效"的真实原因——不是缺陷，是设计如此。
--
-- 这里在测试库里把它关掉，让自动化可以直接登录。
-- 如果要在开启验证码的环境下跑，请改用：
--   AUTOTEST_CAPTCHA_ENABLED=true + AUTOTEST_REDIS_URL=redis://localhost:6379/0
-- 框架会从 Redis 的 captcha_codes:{uuid} 读取真实验证码，同样不需要改后端代码。

UPDATE sys_config
   SET config_value = 'false'
 WHERE config_key = 'sys.account.captchaEnabled';

-- 关掉注册开关，避免公开注册入口在测试环境被误用
UPDATE sys_config
   SET config_value = 'false'
 WHERE config_key = 'sys.account.registerUser';
